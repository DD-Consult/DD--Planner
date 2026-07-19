#!/usr/bin/env python3
"""
DD Planner - Production Data Sync & Migration Script

This script helps diagnose and fix data synchronization issues between
development and production MongoDB databases.

Usage:
    python data_sync.py --check          # Check data differences
    python data_sync.py --export         # Export production data
    python data_sync.py --import FILE    # Import data to current DB
    python data_sync.py --validate       # Validate data integrity
"""

import asyncio
import sys
import json
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import Dict, List, Any

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and ObjectId"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)


class DataSync:
    def __init__(self, mongo_url: str = None, db_name: str = 'resource_planner'):
        self.mongo_url = mongo_url or os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = db_name
        self.client = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        print(f"Connecting to: {self.mongo_url}")
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client[self.db_name]
        
        # Test connection
        await self.client.admin.command('ping')
        print(f"✓ Connected to database: {self.db_name}")
        
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            print("✓ Connection closed")
    
    async def check_collections(self) -> Dict[str, int]:
        """Check all collections and document counts"""
        collections = await self.db.list_collection_names()
        
        counts = {}
        for coll in collections:
            count = await self.db[coll].count_documents({})
            counts[coll] = count
            
        return counts
    
    async def check_data_issues(self):
        """Check for common data integrity issues"""
        print("\n" + "="*80)
        print("DATA INTEGRITY CHECK")
        print("="*80)
        
        issues = []
        
        # Check 1: Projects without phases
        projects_without_phases = await self.db.projects.count_documents({
            '$or': [
                {'phases': {'$exists': False}},
                {'phases': []},
                {'phases': None}
            ]
        })
        
        if projects_without_phases > 0:
            issues.append(f"⚠️  {projects_without_phases} project(s) have no phases defined")
            
            # List them
            projects = await self.db.projects.find({
                '$or': [
                    {'phases': {'$exists': False}},
                    {'phases': []},
                    {'phases': None}
                ]
            }, {'name': 1, 'client_name': 1}).to_list(length=100)
            
            print(f"\nProjects without phases:")
            for p in projects:
                print(f"  - {p.get('name')} ({p.get('client_name')})")
        
        # Check 2: Phases without IDs
        projects_with_bad_phases = await self.db.projects.find({
            'phases': {'$exists': True, '$ne': []}
        }).to_list(length=1000)
        
        bad_phase_projects = []
        for project in projects_with_bad_phases:
            for phase in project.get('phases', []):
                if not phase.get('id') or not phase.get('id').strip():
                    bad_phase_projects.append({
                        'project': project.get('name'),
                        'phase': phase.get('name'),
                        'phase_id': phase.get('id')
                    })
        
        if bad_phase_projects:
            issues.append(f"⚠️  {len(bad_phase_projects)} phase(s) have missing or invalid IDs")
            print(f"\nPhases with bad IDs:")
            for item in bad_phase_projects[:10]:  # Show first 10
                print(f"  - Project: {item['project']}, Phase: {item['phase']}, ID: '{item['phase_id']}'")
        
        # Check 3: Allocations referencing non-existent projects
        allocations = await self.db.allocations.find().to_list(length=10000)
        project_ids = set(str(p['_id']) for p in await self.db.projects.find({}, {'_id': 1}).to_list(length=10000))
        
        orphaned_allocations = [a for a in allocations if a.get('project_id') not in project_ids]
        
        if orphaned_allocations:
            issues.append(f"⚠️  {len(orphaned_allocations)} allocation(s) reference non-existent projects")
        
        # Check 4: Timesheets referencing non-existent projects/resources
        timesheets = await self.db.timesheets.find().to_list(length=10000)
        resource_ids = set(str(r['_id']) for r in await self.db.resources.find({}, {'_id': 1}).to_list(length=10000))
        
        orphaned_timesheets = [
            t for t in timesheets 
            if t.get('project_id') not in project_ids or t.get('resource_id') not in resource_ids
        ]
        
        if orphaned_timesheets:
            issues.append(f"⚠️  {len(orphaned_timesheets)} timesheet(s) reference non-existent projects/resources")
        
        # Check 5: Duplicate user emails
        pipeline = [
            {'$group': {'_id': '$email', 'count': {'$sum': 1}}},
            {'$match': {'count': {'$gt': 1}}}
        ]
        
        duplicates = await self.db.users.aggregate(pipeline).to_list(length=100)
        
        if duplicates:
            issues.append(f"⚠️  {len(duplicates)} duplicate user email(s) found")
            print(f"\nDuplicate emails:")
            for dup in duplicates:
                print(f"  - {dup['_id']} (appears {dup['count']} times)")
        
        # Summary
        print(f"\n{'='*80}")
        if not issues:
            print("✓ No data integrity issues found!")
        else:
            print(f"Found {len(issues)} issue(s):")
            for issue in issues:
                print(f"  {issue}")
        
        return issues
    
    async def export_data(self, output_file: str = None):
        """Export all data to JSON file"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"dd_planner_export_{timestamp}.json"
        
        print(f"\nExporting data to: {output_file}")
        
        data = {
            'metadata': {
                'export_date': datetime.now().isoformat(),
                'database': self.db_name,
                'mongo_url': self.mongo_url.split('@')[0] + '@***' if '@' in self.mongo_url else 'localhost'
            },
            'collections': {}
        }
        
        # Export each collection
        collections = ['users', 'resources', 'projects', 'allocations', 'timesheets', 
                      'status_updates', 'risks', 'holidays', 'leaves', 'allocation_roles']
        
        for coll_name in collections:
            if coll_name in await self.db.list_collection_names():
                docs = await self.db[coll_name].find().to_list(length=100000)
                data['collections'][coll_name] = docs
                print(f"  ✓ Exported {len(docs)} documents from {coll_name}")
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, cls=DateTimeEncoder)
        
        print(f"\n✓ Export complete: {output_file}")
        
        # Show file size
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"  File size: {size_mb:.2f} MB")
        
        return output_file
    
    async def import_data(self, input_file: str, dry_run: bool = True):
        """Import data from JSON file"""
        print(f"\nImporting data from: {input_file}")
        
        if dry_run:
            print("⚠️  DRY RUN MODE - No changes will be made")
        
        # Read file
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        print(f"\nExport metadata:")
        print(f"  Date: {data['metadata']['export_date']}")
        print(f"  Source DB: {data['metadata']['database']}")
        
        # Import each collection
        for coll_name, docs in data['collections'].items():
            print(f"\n{coll_name}: {len(docs)} documents")
            
            if not dry_run:
                # Clear existing data (DANGEROUS!)
                await self.db[coll_name].delete_many({})
                
                # Convert string IDs back to ObjectId
                for doc in docs:
                    if '_id' in doc and isinstance(doc['_id'], str):
                        try:
                            doc['_id'] = ObjectId(doc['_id'])
                        except:
                            pass
                
                # Insert documents
                if docs:
                    await self.db[coll_name].insert_many(docs)
                
                print(f"  ✓ Imported {len(docs)} documents")
            else:
                print(f"  Would import {len(docs)} documents")
        
        if dry_run:
            print("\n⚠️  This was a DRY RUN. Run with --no-dry-run to actually import.")
        else:
            print("\n✓ Import complete!")
    
    async def compare_databases(self, prod_url: str):
        """Compare current database with production"""
        print("\n" + "="*80)
        print("DATABASE COMPARISON")
        print("="*80)
        
        # Connect to production
        prod_client = AsyncIOMotorClient(prod_url)
        prod_db = prod_client[self.db_name]
        
        print(f"\nLocal:      {self.mongo_url}")
        print(f"Production: {prod_url.split('@')[0] + '@***' if '@' in prod_url else prod_url}")
        
        # Compare collections
        local_colls = set(await self.db.list_collection_names())
        prod_colls = set(await prod_db.list_collection_names())
        
        print(f"\nCollections:")
        print(f"  Local only: {local_colls - prod_colls}")
        print(f"  Prod only:  {prod_colls - local_colls}")
        print(f"  Both:       {local_colls & prod_colls}")
        
        # Compare document counts
        print(f"\nDocument counts:")
        print(f"{'Collection':<20} {'Local':<10} {'Production':<12} {'Diff'}")
        print("-" * 50)
        
        for coll in sorted(local_colls & prod_colls):
            local_count = await self.db[coll].count_documents({})
            prod_count = await prod_db[coll].count_documents({})
            diff = prod_count - local_count
            
            diff_str = f"+{diff}" if diff > 0 else str(diff) if diff < 0 else "="
            print(f"{coll:<20} {local_count:<10} {prod_count:<12} {diff_str}")
        
        prod_client.close()
        
        print("\n" + "="*80)


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DD Planner Data Sync Tool')
    parser.add_argument('--check', action='store_true', help='Check data integrity')
    parser.add_argument('--export', action='store_true', help='Export data to JSON')
    parser.add_argument('--import-file', type=str, help='Import data from JSON file')
    parser.add_argument('--compare', type=str, help='Compare with production database URL')
    parser.add_argument('--mongo-url', type=str, help='MongoDB connection URL')
    parser.add_argument('--no-dry-run', action='store_true', help='Actually perform import (dangerous!)')
    
    args = parser.parse_args()
    
    # Create sync instance
    sync = DataSync(mongo_url=args.mongo_url)
    
    try:
        await sync.connect()
        
        # Show current database status
        counts = await sync.check_collections()
        print(f"\nCurrent database collections:")
        for coll, count in sorted(counts.items()):
            print(f"  {coll}: {count} documents")
        
        # Execute requested operation
        if args.check:
            await sync.check_data_issues()
        
        elif args.export:
            await sync.export_data()
        
        elif args.import_file:
            await sync.import_data(args.import_file, dry_run=not args.no_dry_run)
        
        elif args.compare:
            await sync.compare_databases(args.compare)
        
        else:
            print("\nNo operation specified. Use --help for options.")
            print("\nQuick commands:")
            print("  python data_sync.py --check              # Check for data issues")
            print("  python data_sync.py --export             # Export current data")
            print("  python data_sync.py --compare PROD_URL   # Compare with production")
        
    finally:
        await sync.close()


if __name__ == '__main__':
    asyncio.run(main())

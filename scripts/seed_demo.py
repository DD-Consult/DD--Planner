#!/usr/bin/env python3
"""
Idempotent demo user and dataset seeding script for DD Planner public demo.

Creates:
- A demo user (demo@ddplanner.app) with admin role and is_demo flag
- A small, realistic demo dataset (2-3 projects, resources, allocations, WBS tasks, risks)
- All demo data is tagged with demo_seed: true for easy identification/cleanup

Safe to run multiple times - uses stable IDs where possible and upserts to avoid duplicates.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Add backend to path so we can import dependencies
sys.path.insert(0, '/app/backend')
from auth.dependencies import get_password_hash


def load_env():
    """Load environment variables from .env file."""
    env_path = '/app/backend/.env'
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value


async def seed_demo():
    """Create/update demo user and demo dataset."""
    load_env()
    
    # Get DB connection details from environment
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'resource_planner')
    
    print(f"📦 Connecting to MongoDB: {mongo_url}")
    print(f"📦 Database: {db_name}")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        # === Step 1: Create/ensure demo user ===
        print("\n🔍 Creating demo user...")
        
        demo_email = "demo@ddplanner.app"
        demo_user = await db.users.find_one({"email": demo_email})
        
        if demo_user:
            print(f"✅ Demo user already exists: {demo_email}")
            # Ensure is_demo flag is set
            await db.users.update_one(
                {"email": demo_email},
                {"$set": {"is_demo": True}}
            )
        else:
            # Create demo user with random password (not used - demo-login doesn't require it)
            demo_user_doc = {
                "email": demo_email,
                "password_hash": get_password_hash(str(uuid.uuid4())),  # Random hash
                "role": "admin",  # Admin so demo tour can see the whole app
                "is_demo": True,
                "allowed_project_ids": []
            }
            result = await db.users.insert_one(demo_user_doc)
            demo_user = await db.users.find_one({"_id": result.inserted_id})
            print(f"✅ Created demo user: {demo_email}")
        
        # === Step 2: Create demo resources ===
        print("\n👥 Creating demo resources...")
        
        demo_resources = [
            {"name": "Sarah Chen", "role": "Senior Developer", "standard_capacity": 100, 
             "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=SarahChen", "demo_seed": True},
            {"name": "Michael Torres", "role": "UX Designer", "standard_capacity": 100,
             "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=MichaelTorres", "demo_seed": True},
            {"name": "Emma Rodriguez", "role": "Project Manager", "standard_capacity": 100,
             "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=EmmaRodriguez", "demo_seed": True},
            {"name": "James Park", "role": "Backend Developer", "standard_capacity": 100,
             "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=JamesPark", "demo_seed": True},
        ]
        
        resource_ids = []
        for res in demo_resources:
            existing = await db.resources.find_one({"name": res["name"], "demo_seed": True})
            if existing:
                resource_ids.append(str(existing["_id"]))
                print(f"  ✓ Resource exists: {res['name']}")
            else:
                result = await db.resources.insert_one(res)
                resource_ids.append(str(result.inserted_id))
                print(f"  ✓ Created resource: {res['name']}")
        
        # === Step 3: Create demo projects ===
        print("\n📂 Creating demo projects...")
        
        today = datetime.now(timezone.utc)
        demo_projects = [
            {
                "name": "E-Commerce Platform Redesign",
                "client_name": "RetailCo",
                "status": "Active",
                "start_date": today,
                "end_date": today + timedelta(days=60),
                "budgeted_hours": 480,
                "project_objective": "Modernize the checkout experience and improve mobile responsiveness",
                "health": "Green",
                "schedule_status": "On Track",
                "actual_progress": 35.0,
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Discovery & Design",
                        "start_date": today,
                        "end_date": today + timedelta(days=20),
                        "status": "Active"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Development",
                        "start_date": today + timedelta(days=20),
                        "end_date": today + timedelta(days=50),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Testing & Launch",
                        "start_date": today + timedelta(days=50),
                        "end_date": today + timedelta(days=60),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            },
            {
                "name": "Mobile Banking App",
                "client_name": "FinTech Solutions",
                "status": "Active",
                "start_date": today - timedelta(days=10),
                "end_date": today + timedelta(days=50),
                "budgeted_hours": 640,
                "project_objective": "Build a secure mobile banking application with biometric authentication",
                "health": "Amber",
                "schedule_status": "At Risk",
                "actual_progress": 25.0,
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Architecture & Security",
                        "start_date": today - timedelta(days=10),
                        "end_date": today + timedelta(days=15),
                        "status": "Active"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Core Features",
                        "start_date": today + timedelta(days=15),
                        "end_date": today + timedelta(days=45),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            },
            {
                "name": "Data Analytics Dashboard",
                "client_name": "Analytics Inc",
                "status": "Pipeline",
                "start_date": today + timedelta(days=14),
                "end_date": today + timedelta(days=70),
                "budgeted_hours": 320,
                "project_objective": "Create a real-time analytics dashboard for business intelligence",
                "health": "Green",
                "schedule_status": "On Track",
                "actual_progress": 0.0,
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Planning",
                        "start_date": today + timedelta(days=14),
                        "end_date": today + timedelta(days=28),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Implementation",
                        "start_date": today + timedelta(days=28),
                        "end_date": today + timedelta(days=70),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            }
        ]
        
        project_ids = []
        for proj in demo_projects:
            existing = await db.projects.find_one({"name": proj["name"], "demo_seed": True})
            if existing:
                project_ids.append(str(existing["_id"]))
                print(f"  ✓ Project exists: {proj['name']}")
            else:
                result = await db.projects.insert_one(proj)
                project_ids.append(str(result.inserted_id))
                print(f"  ✓ Created project: {proj['name']}")
        
        # === Step 4: Create demo allocations ===
        print("\n🔗 Creating demo allocations...")
        
        demo_allocations = [
            # E-Commerce Platform - multiple resources
            {"resource_id": resource_ids[0], "project_id": project_ids[0], 
             "start_date": today, "end_date": today + timedelta(days=60), 
             "percentage": 80, "role": "Senior Developer", "demo_seed": True},
            {"resource_id": resource_ids[1], "project_id": project_ids[0], 
             "start_date": today, "end_date": today + timedelta(days=20), 
             "percentage": 60, "role": "UX Designer", "demo_seed": True},
            {"resource_id": resource_ids[2], "project_id": project_ids[0], 
             "start_date": today, "end_date": today + timedelta(days=60), 
             "percentage": 50, "role": "Project Manager", "demo_seed": True},
            
            # Mobile Banking App
            {"resource_id": resource_ids[0], "project_id": project_ids[1], 
             "start_date": today - timedelta(days=10), "end_date": today + timedelta(days=50), 
             "percentage": 20, "role": "Senior Developer", "demo_seed": True},
            {"resource_id": resource_ids[3], "project_id": project_ids[1], 
             "start_date": today - timedelta(days=10), "end_date": today + timedelta(days=50), 
             "percentage": 100, "role": "Backend Developer", "demo_seed": True},
            {"resource_id": resource_ids[2], "project_id": project_ids[1], 
             "start_date": today - timedelta(days=10), "end_date": today + timedelta(days=50), 
             "percentage": 30, "role": "Project Manager", "demo_seed": True},
            
            # Data Analytics Dashboard (future)
            {"resource_id": resource_ids[1], "project_id": project_ids[2], 
             "start_date": today + timedelta(days=20), "end_date": today + timedelta(days=70), 
             "percentage": 40, "role": "UX Designer", "demo_seed": True},
        ]
        
        allocation_count = 0
        for alloc in demo_allocations:
            existing = await db.allocations.find_one({
                "resource_id": alloc["resource_id"],
                "project_id": alloc["project_id"],
                "demo_seed": True
            })
            if not existing:
                await db.allocations.insert_one(alloc)
                allocation_count += 1
        
        print(f"  ✓ Created {allocation_count} allocations")
        
        # === Step 5: Create demo WBS tasks ===
        print("\n📋 Creating demo WBS tasks...")
        
        # Get project phases for the first project
        first_project = await db.projects.find_one({"_id": ObjectId(project_ids[0])})
        phase_1 = first_project["phases"][0]["id"] if first_project and first_project.get("phases") else None
        phase_2 = first_project["phases"][1]["id"] if first_project and len(first_project.get("phases", [])) > 1 else None
        
        demo_tasks = [
            # E-Commerce Platform tasks
            {
                "project_id": project_ids[0],
                "name": "User Research & Personas",
                "description": "Conduct user interviews and create buyer personas",
                "phase_id": phase_1,
                "phase_name": "Discovery & Design",
                "assigned_to": resource_ids[1],
                "status": "done",
                "priority": "high",
                "estimated_hours": 40,
                "actual_hours": 42,
                "progress_percentage": 100,
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
                "order": 1,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "Wireframes & Mockups",
                "description": "Create high-fidelity designs for checkout flow",
                "phase_id": phase_1,
                "phase_name": "Discovery & Design",
                "assigned_to": resource_ids[1],
                "status": "in_progress",
                "priority": "high",
                "estimated_hours": 60,
                "actual_hours": 35,
                "progress_percentage": 60,
                "start_date": (today + timedelta(days=7)).isoformat(),
                "end_date": (today + timedelta(days=20)).isoformat(),
                "order": 2,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "API Integration",
                "description": "Integrate payment gateway and inventory APIs",
                "phase_id": phase_2,
                "phase_name": "Development",
                "assigned_to": resource_ids[0],
                "status": "todo",
                "priority": "critical",
                "estimated_hours": 80,
                "actual_hours": 0,
                "progress_percentage": 0,
                "start_date": (today + timedelta(days=20)).isoformat(),
                "end_date": (today + timedelta(days=35)).isoformat(),
                "order": 3,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "Checkout Flow Implementation",
                "description": "Build the new checkout UI components and flow",
                "phase_id": phase_2,
                "phase_name": "Development",
                "assigned_to": resource_ids[0],
                "status": "todo",
                "priority": "high",
                "estimated_hours": 100,
                "actual_hours": 0,
                "progress_percentage": 0,
                "start_date": (today + timedelta(days=20)).isoformat(),
                "end_date": (today + timedelta(days=40)).isoformat(),
                "order": 4,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "Mobile Responsiveness",
                "description": "Ensure all pages work perfectly on mobile devices",
                "phase_id": phase_2,
                "phase_name": "Development",
                "assigned_to": resource_ids[0],
                "status": "todo",
                "priority": "medium",
                "estimated_hours": 60,
                "actual_hours": 0,
                "progress_percentage": 0,
                "start_date": (today + timedelta(days=35)).isoformat(),
                "end_date": (today + timedelta(days=47)).isoformat(),
                "order": 5,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "QA Testing",
                "description": "End-to-end testing of checkout process",
                "phase_id": first_project["phases"][2]["id"] if len(first_project.get("phases", [])) > 2 else None,
                "phase_name": "Testing & Launch",
                "assigned_to": None,
                "status": "todo",
                "priority": "high",
                "estimated_hours": 40,
                "actual_hours": 0,
                "progress_percentage": 0,
                "start_date": (today + timedelta(days=50)).isoformat(),
                "end_date": (today + timedelta(days=57)).isoformat(),
                "order": 6,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "name": "Production Launch",
                "description": "Deploy to production and monitor",
                "phase_id": first_project["phases"][2]["id"] if len(first_project.get("phases", [])) > 2 else None,
                "phase_name": "Testing & Launch",
                "assigned_to": resource_ids[2],
                "status": "todo",
                "priority": "critical",
                "estimated_hours": 20,
                "actual_hours": 0,
                "progress_percentage": 0,
                "is_milestone": True,
                "milestone_date": (today + timedelta(days=60)).isoformat(),
                "start_date": (today + timedelta(days=57)).isoformat(),
                "end_date": (today + timedelta(days=60)).isoformat(),
                "order": 7,
                "dependencies": [],
                "demo_seed": True
            },
            
            # Mobile Banking App tasks
            {
                "project_id": project_ids[1],
                "name": "Security Architecture Design",
                "description": "Design secure authentication and data encryption",
                "phase_id": None,
                "assigned_to": resource_ids[3],
                "status": "in_progress",
                "priority": "critical",
                "estimated_hours": 80,
                "actual_hours": 45,
                "progress_percentage": 55,
                "start_date": (today - timedelta(days=10)).isoformat(),
                "end_date": (today + timedelta(days=5)).isoformat(),
                "order": 1,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[1],
                "name": "Biometric Authentication",
                "description": "Implement fingerprint and face ID login",
                "phase_id": None,
                "assigned_to": resource_ids[3],
                "status": "todo",
                "priority": "high",
                "estimated_hours": 100,
                "actual_hours": 0,
                "progress_percentage": 0,
                "start_date": (today + timedelta(days=5)).isoformat(),
                "end_date": (today + timedelta(days=25)).isoformat(),
                "order": 2,
                "dependencies": [],
                "demo_seed": True
            },
            {
                "project_id": project_ids[1],
                "name": "Account Dashboard",
                "description": "Build main account overview and balance display",
                "phase_id": None,
                "assigned_to": resource_ids[0],
                "status": "in_progress",
                "priority": "high",
                "estimated_hours": 60,
                "actual_hours": 20,
                "progress_percentage": 30,
                "start_date": (today - timedelta(days=5)).isoformat(),
                "end_date": (today + timedelta(days=15)).isoformat(),
                "order": 3,
                "dependencies": [],
                "demo_seed": True
            },
        ]
        
        task_count = 0
        for task in demo_tasks:
            existing = await db.wbs_tasks.find_one({
                "project_id": task["project_id"],
                "name": task["name"],
                "demo_seed": True
            })
            if not existing:
                await db.wbs_tasks.insert_one(task)
                task_count += 1
        
        print(f"  ✓ Created {task_count} WBS tasks")
        
        # === Step 6: Create demo risks ===
        print("\n⚠️  Creating demo risks...")
        
        demo_risks = [
            {
                "project_id": project_ids[0],
                "description": "Payment gateway integration may face API rate limits during peak traffic",
                "impact": "High",
                "probability": "Medium",
                "mitigation": "Implement request throttling and caching; negotiate higher rate limits",
                "status": "Active",
                "category": "Risk",
                "impact_areas": ["Technical", "Schedule"],
                "demo_seed": True
            },
            {
                "project_id": project_ids[0],
                "description": "Mobile browser compatibility issues may require additional testing cycles",
                "impact": "Medium",
                "probability": "Medium",
                "mitigation": "Start cross-browser testing early; allocate buffer time for fixes",
                "status": "Active",
                "category": "Risk",
                "impact_areas": ["Technical", "Quality"],
                "demo_seed": True
            },
            {
                "project_id": project_ids[1],
                "description": "Biometric authentication requirements vary by device/OS version",
                "impact": "High",
                "probability": "High",
                "mitigation": "Thorough device testing matrix; fallback to PIN-based auth",
                "status": "Active",
                "category": "Risk",
                "impact_areas": ["Technical", "Security"],
                "demo_seed": True
            },
            {
                "project_id": project_ids[1],
                "description": "Security audit timeline may extend beyond planned schedule",
                "impact": "High",
                "probability": "Medium",
                "mitigation": "Engage security auditors early; schedule buffer time",
                "status": "Active",
                "category": "Risk",
                "impact_areas": ["Schedule", "Compliance"],
                "demo_seed": True
            },
        ]
        
        risk_count = 0
        for risk in demo_risks:
            existing = await db.risks.find_one({
                "project_id": risk["project_id"],
                "description": risk["description"],
                "demo_seed": True
            })
            if not existing:
                await db.risks.insert_one(risk)
                risk_count += 1
        
        print(f"  ✓ Created {risk_count} risks")
        
        # === Summary ===
        print("\n" + "="*60)
        print("✅ DEMO SEED COMPLETE")
        print("="*60)
        print(f"Demo User: {demo_email}")
        print(f"  Role: admin")
        print(f"  is_demo: True")
        print(f"\nDemo Data Created:")
        print(f"  • {len(demo_resources)} resources")
        print(f"  • {len(demo_projects)} projects")
        print(f"  • {len(demo_allocations)} allocations")
        print(f"  • {len(demo_tasks)} WBS tasks")
        print(f"  • {len(demo_risks)} risks")
        print(f"\nAll demo data is tagged with: demo_seed=true")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error during seed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed_demo())

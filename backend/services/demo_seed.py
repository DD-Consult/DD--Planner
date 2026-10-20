"""DD Planner Demo Dataset Seeder

IDEMPOTENT async seeder that populates a rich, fully-FAKE demo dataset using
the app's LazyCollection handles. Writes to whatever DB is currently bound via
the ContextVar — the caller binds an isolated demo DB before calling this.

Usage:
    from services.demo_seed import seed_demo_dataset
    
    # Bind demo DB context
    from database import set_current_tenant_db, get_demo_db
    token = set_current_tenant_db(get_demo_db())
    try:
        result = await seed_demo_dataset()
    finally:
        reset_current_tenant_db(token)

Design:
    - Uses LazyCollection imports from database.py (NOT MongoClient)
    - Tags every doc with demo_seed: True
    - Idempotent: safe to run repeatedly (checks if dataset exists)
    - Returns summary dict of counts
"""
from datetime import datetime, timedelta, timezone, date
from bson import ObjectId
import uuid
import secrets

# Import LazyCollection handles (resolve to current DB at call-time)
from database import (
    projects_collection,
    resources_collection,
    allocations_collection,
    wbs_tasks_collection,
    risks_collection,
    status_updates_collection,
    timesheets_collection,
    holidays_collection,
    proposals_collection,
    report_links_collection,
)
from services.proposals.renderer import load_sample_brief


async def seed_demo_dataset() -> dict:
    """Seed the demo dataset. Idempotent — safe to run multiple times.
    
    Returns:
        dict: Summary of seeded counts per collection
    """
    # === IDEMPOTENCY GUARD ===
    # If demo projects already exist, skip seeding
    existing_count = await projects_collection.count_documents({"demo_seed": True})
    if existing_count > 0:
        return {
            "status": "already_seeded",
            "message": "Demo dataset already exists (found projects with demo_seed=True)"
        }
    
    counts = {
        "resources": 0,
        "projects": 0,
        "allocations": 0,
        "wbs_tasks": 0,
        "risks": 0,
        "status_updates": 0,
        "timesheets": 0,
        "holidays": 0,
        "proposals": 0,
        "report_links": 0,
    }
    
    today = datetime.now(timezone.utc)
    
    # =================================================================
    # 1. RESOURCES (5-6 fake people)
    # =================================================================
    try:
        demo_resources = [
            {
                "name": "Sarah Chen",
                "role": "Senior Developer",
                "standard_capacity": 100,
                "active": True,
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=SarahChen",
                "demo_seed": True
            },
            {
                "name": "Michael Torres",
                "role": "Project Manager",
                "standard_capacity": 100,
                "active": True,
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=MichaelTorres",
                "demo_seed": True
            },
            {
                "name": "Emma Rodriguez",
                "role": "UX Designer",
                "standard_capacity": 100,
                "active": True,
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=EmmaRodriguez",
                "demo_seed": True
            },
            {
                "name": "James Park",
                "role": "Backend Developer",
                "standard_capacity": 100,
                "active": True,
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=JamesPark",
                "demo_seed": True
            },
            {
                "name": "Olivia Bennett",
                "role": "QA Engineer",
                "standard_capacity": 60,  # Part-time
                "active": True,
                "avatar_url": "https://api.dicebear.com/7.x/avataaars/svg?seed=OliviaBennett",
                "demo_seed": True
            },
        ]
        
        resource_ids = []
        for res in demo_resources:
            result = await resources_collection.insert_one(res)
            resource_ids.append(str(result.inserted_id))
            counts["resources"] += 1
        
        print(f"✓ Created {counts['resources']} resources")
    except Exception as e:
        print(f"✗ Resource seeding failed: {e}")
    
    # =================================================================
    # 2. PROJECTS (4 with realistic fake client names and phases)
    # =================================================================
    try:
        demo_projects = [
            {
                "name": "E-Commerce Platform Modernization",
                "client_name": "Northwind Retail",
                "status": "Active",
                "start_date": today - timedelta(days=15),
                "end_date": today + timedelta(days=60),
                "budgeted_hours": 560,
                "project_objective": "Modernize checkout experience, improve mobile responsiveness, and integrate new payment gateway",
                "health": "Green",
                "schedule_status": "On Track",
                "actual_progress": 42.0,
                "main_contact_name": "Jennifer Blake",
                "main_contact_email": "jennifer.blake@northwind-demo.test",
                "created_at": today - timedelta(days=15),
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Discovery & Design",
                        "start_date": today - timedelta(days=15),
                        "end_date": today + timedelta(days=10),
                        "status": "Active"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Development",
                        "start_date": today + timedelta(days=10),
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
                "name": "Supply Chain Optimization Platform",
                "client_name": "Apex Logistics",
                "status": "Active",
                "start_date": today - timedelta(days=30),
                "end_date": today + timedelta(days=45),
                "budgeted_hours": 720,
                "project_objective": "Build real-time inventory tracking and predictive analytics dashboard",
                "health": "Amber",
                "schedule_status": "At Risk",
                "actual_progress": 55.0,
                "main_contact_name": "Marcus Chen",
                "main_contact_email": "marcus.chen@apexlogistics-demo.test",
                "created_at": today - timedelta(days=30),
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Planning & Architecture",
                        "start_date": today - timedelta(days=30),
                        "end_date": today - timedelta(days=5),
                        "status": "Completed"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Core Development",
                        "start_date": today - timedelta(days=5),
                        "end_date": today + timedelta(days=35),
                        "status": "Active"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Integration & Testing",
                        "start_date": today + timedelta(days=35),
                        "end_date": today + timedelta(days=45),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            },
            {
                "name": "Patient Portal Development",
                "client_name": "Brightpath Health",
                "status": "Active",
                "start_date": today,
                "end_date": today + timedelta(days=90),
                "budgeted_hours": 480,
                "project_objective": "Secure patient portal with appointment scheduling, medical records access, and telehealth integration",
                "health": "Green",
                "schedule_status": "On Track",
                "actual_progress": 15.0,
                "main_contact_name": "Dr. Sarah Mitchell",
                "main_contact_email": "sarah.mitchell@brightpath-demo.test",
                "created_at": today,
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Requirements & Design",
                        "start_date": today,
                        "end_date": today + timedelta(days=20),
                        "status": "Active"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Development",
                        "start_date": today + timedelta(days=20),
                        "end_date": today + timedelta(days=70),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Security Audit & Launch",
                        "start_date": today + timedelta(days=70),
                        "end_date": today + timedelta(days=90),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            },
            {
                "name": "Digital Banking Transformation",
                "client_name": "Coastal Credit Union",
                "status": "Pipeline",
                "start_date": today + timedelta(days=30),
                "end_date": today + timedelta(days=120),
                "budgeted_hours": 960,
                "project_objective": "Complete digital banking platform with mobile apps, AI-powered fraud detection, and biometric authentication",
                "health": "Green",
                "schedule_status": "Not Started",
                "actual_progress": 0.0,
                "main_contact_name": "Robert Kim",
                "main_contact_email": "robert.kim@coastalcu-demo.test",
                "created_at": today - timedelta(days=5),
                "phases": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Discovery",
                        "start_date": today + timedelta(days=30),
                        "end_date": today + timedelta(days=45),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Architecture",
                        "start_date": today + timedelta(days=45),
                        "end_date": today + timedelta(days=60),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Development",
                        "start_date": today + timedelta(days=60),
                        "end_date": today + timedelta(days=110),
                        "status": "Pending"
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Testing & Launch",
                        "start_date": today + timedelta(days=110),
                        "end_date": today + timedelta(days=120),
                        "status": "Pending"
                    }
                ],
                "demo_seed": True
            },
        ]
        
        project_ids = []
        project_docs = []
        for proj in demo_projects:
            result = await projects_collection.insert_one(proj)
            project_ids.append(str(result.inserted_id))
            proj["_id"] = result.inserted_id
            project_docs.append(proj)
            counts["projects"] += 1
        
        print(f"✓ Created {counts['projects']} projects")
    except Exception as e:
        print(f"✗ Project seeding failed: {e}")
        project_ids = []
        project_docs = []
    
    # =================================================================
    # 3. ALLOCATIONS (8-12, with over-allocations)
    # =================================================================
    if len(resource_ids) > 0 and len(project_ids) > 0:
        try:
            demo_allocations = [
                # Northwind Retail (Project 0)
                {
                    "resource_id": resource_ids[0],  # Sarah Chen
                    "project_id": project_ids[0],
                    "start_date": today - timedelta(days=15),
                    "end_date": today + timedelta(days=60),
                    "percentage": 80,
                    "role": "Senior Developer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[2],  # Emma Rodriguez
                    "project_id": project_ids[0],
                    "start_date": today - timedelta(days=15),
                    "end_date": today + timedelta(days=10),
                    "percentage": 60,
                    "role": "UX Designer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[1],  # Michael Torres
                    "project_id": project_ids[0],
                    "start_date": today - timedelta(days=15),
                    "end_date": today + timedelta(days=60),
                    "percentage": 30,
                    "role": "Project Manager",
                    "demo_seed": True
                },
                
                # Apex Logistics (Project 1)
                {
                    "resource_id": resource_ids[3],  # James Park
                    "project_id": project_ids[1],
                    "start_date": today - timedelta(days=30),
                    "end_date": today + timedelta(days=45),
                    "percentage": 100,
                    "role": "Backend Developer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[0],  # Sarah Chen (creates over-allocation)
                    "project_id": project_ids[1],
                    "start_date": today - timedelta(days=10),
                    "end_date": today + timedelta(days=30),
                    "percentage": 40,  # 80 + 40 = 120% over-allocated!
                    "role": "Technical Lead",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[1],  # Michael Torres
                    "project_id": project_ids[1],
                    "start_date": today - timedelta(days=30),
                    "end_date": today + timedelta(days=45),
                    "percentage": 40,
                    "role": "Project Manager",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[4],  # Olivia Bennett
                    "project_id": project_ids[1],
                    "start_date": today + timedelta(days=20),
                    "end_date": today + timedelta(days=45),
                    "percentage": 60,
                    "role": "QA Engineer",
                    "demo_seed": True
                },
                
                # Brightpath Health (Project 2)
                {
                    "resource_id": resource_ids[2],  # Emma Rodriguez
                    "project_id": project_ids[2],
                    "start_date": today,
                    "end_date": today + timedelta(days=20),
                    "percentage": 50,
                    "role": "UX Designer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[3],  # James Park
                    "project_id": project_ids[2],
                    "start_date": today + timedelta(days=20),
                    "end_date": today + timedelta(days=90),
                    "percentage": 70,
                    "role": "Backend Developer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[1],  # Michael Torres (creates over-allocation)
                    "project_id": project_ids[2],
                    "start_date": today,
                    "end_date": today + timedelta(days=90),
                    "percentage": 50,  # 30 + 40 + 50 = 120% over-allocated during overlap!
                    "role": "Project Manager",
                    "demo_seed": True
                },
                
                # Coastal Credit Union (Pipeline - future)
                {
                    "resource_id": resource_ids[0],  # Sarah Chen
                    "project_id": project_ids[3],
                    "start_date": today + timedelta(days=60),
                    "end_date": today + timedelta(days=120),
                    "percentage": 50,
                    "role": "Senior Developer",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[2],  # Emma Rodriguez
                    "project_id": project_ids[3],
                    "start_date": today + timedelta(days=30),
                    "end_date": today + timedelta(days=50),
                    "percentage": 40,
                    "role": "UX Designer",
                    "demo_seed": True
                },
            ]
            
            for alloc in demo_allocations:
                await allocations_collection.insert_one(alloc)
                counts["allocations"] += 1
            
            print(f"✓ Created {counts['allocations']} allocations")
        except Exception as e:
            print(f"✗ Allocation seeding failed: {e}")
    
    # =================================================================
    # 4. WBS TASKS (per Active project, 6-10 tasks each with dependencies)
    # =================================================================
    if len(project_ids) >= 3 and len(resource_ids) > 0:
        try:
            # Get phase IDs for first 3 projects (Active)
            p0_phases = project_docs[0]["phases"]
            p1_phases = project_docs[1]["phases"]
            p2_phases = project_docs[2]["phases"]
            
            demo_tasks = []
            
            # --- Northwind Retail Tasks (Project 0) ---
            task_ids_p0 = [str(uuid.uuid4()) for _ in range(8)]
            
            demo_tasks.extend([
                {
                    "project_id": project_ids[0],
                    "name": "User Research & Personas",
                    "description": "Conduct user interviews and create buyer personas",
                    "phase_id": p0_phases[0]["id"],
                    "phase_name": p0_phases[0]["name"],
                    "assigned_to": resource_ids[2],  # Emma
                    "status": "done",
                    "priority": "high",
                    "estimated_hours": 40,
                    "actual_hours": 42,
                    "progress_percentage": 100,
                    "start_date": (today - timedelta(days=15)).isoformat(),
                    "end_date": (today - timedelta(days=8)).isoformat(),
                    "order": 1,
                    "dependencies": [],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[0]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Wireframes & Mockups",
                    "description": "Create high-fidelity designs for checkout flow",
                    "phase_id": p0_phases[0]["id"],
                    "phase_name": p0_phases[0]["name"],
                    "assigned_to": resource_ids[2],  # Emma
                    "status": "in_progress",
                    "priority": "high",
                    "estimated_hours": 60,
                    "actual_hours": 35,
                    "progress_percentage": 60,
                    "start_date": (today - timedelta(days=8)).isoformat(),
                    "end_date": (today + timedelta(days=10)).isoformat(),
                    "order": 2,
                    "dependencies": [task_ids_p0[0]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[1]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Database Schema Design",
                    "description": "Design optimized database schema for new features",
                    "phase_id": p0_phases[1]["id"],
                    "phase_name": p0_phases[1]["name"],
                    "assigned_to": resource_ids[0],  # Sarah
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 30,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=10)).isoformat(),
                    "end_date": (today + timedelta(days=17)).isoformat(),
                    "order": 3,
                    "dependencies": [task_ids_p0[1]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[2]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Payment Gateway Integration",
                    "description": "Integrate new payment provider APIs",
                    "phase_id": p0_phases[1]["id"],
                    "phase_name": p0_phases[1]["name"],
                    "assigned_to": resource_ids[0],  # Sarah
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 80,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=17)).isoformat(),
                    "end_date": (today + timedelta(days=32)).isoformat(),
                    "order": 4,
                    "dependencies": [task_ids_p0[2]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[3]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Checkout Flow Implementation",
                    "description": "Build new checkout UI components",
                    "phase_id": p0_phases[1]["id"],
                    "phase_name": p0_phases[1]["name"],
                    "assigned_to": resource_ids[0],  # Sarah
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 100,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=20)).isoformat(),
                    "end_date": (today + timedelta(days=40)).isoformat(),
                    "order": 5,
                    "dependencies": [task_ids_p0[2]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[4]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Mobile Responsiveness",
                    "description": "Ensure all pages work perfectly on mobile",
                    "phase_id": p0_phases[1]["id"],
                    "phase_name": p0_phases[1]["name"],
                    "assigned_to": resource_ids[0],  # Sarah
                    "status": "todo",
                    "priority": "medium",
                    "estimated_hours": 60,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=35)).isoformat(),
                    "end_date": (today + timedelta(days=47)).isoformat(),
                    "order": 6,
                    "dependencies": [task_ids_p0[4]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[5]
                },
                {
                    "project_id": project_ids[0],
                    "name": "End-to-End QA Testing",
                    "description": "Comprehensive testing of checkout process",
                    "phase_id": p0_phases[2]["id"],
                    "phase_name": p0_phases[2]["name"],
                    "assigned_to": None,
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 40,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=50)).isoformat(),
                    "end_date": (today + timedelta(days=57)).isoformat(),
                    "order": 7,
                    "dependencies": [task_ids_p0[3], task_ids_p0[5]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[6]
                },
                {
                    "project_id": project_ids[0],
                    "name": "Production Launch",
                    "description": "Deploy to production and monitor",
                    "phase_id": p0_phases[2]["id"],
                    "phase_name": p0_phases[2]["name"],
                    "assigned_to": resource_ids[1],  # Michael
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 20,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "is_milestone": True,
                    "milestone_date": (today + timedelta(days=60)).isoformat(),
                    "start_date": (today + timedelta(days=57)).isoformat(),
                    "end_date": (today + timedelta(days=60)).isoformat(),
                    "order": 8,
                    "dependencies": [task_ids_p0[6]],
                    "demo_seed": True,
                    "_task_id": task_ids_p0[7]
                },
            ])
            
            # --- Apex Logistics Tasks (Project 1) ---
            task_ids_p1 = [str(uuid.uuid4()) for _ in range(7)]
            
            demo_tasks.extend([
                {
                    "project_id": project_ids[1],
                    "name": "Architecture Design Review",
                    "description": "Review and finalize system architecture",
                    "phase_id": p1_phases[0]["id"],
                    "phase_name": p1_phases[0]["name"],
                    "assigned_to": resource_ids[3],  # James
                    "status": "done",
                    "priority": "critical",
                    "estimated_hours": 40,
                    "actual_hours": 45,
                    "progress_percentage": 100,
                    "start_date": (today - timedelta(days=30)).isoformat(),
                    "end_date": (today - timedelta(days=20)).isoformat(),
                    "order": 1,
                    "dependencies": [],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[0]
                },
                {
                    "project_id": project_ids[1],
                    "name": "Real-time Tracking Engine",
                    "description": "Build core tracking service with WebSocket support",
                    "phase_id": p1_phases[1]["id"],
                    "phase_name": p1_phases[1]["name"],
                    "assigned_to": resource_ids[3],  # James
                    "status": "in_progress",
                    "priority": "critical",
                    "estimated_hours": 120,
                    "actual_hours": 85,
                    "progress_percentage": 70,
                    "start_date": (today - timedelta(days=20)).isoformat(),
                    "end_date": (today + timedelta(days=15)).isoformat(),
                    "order": 2,
                    "dependencies": [task_ids_p1[0]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[1]
                },
                {
                    "project_id": project_ids[1],
                    "name": "Predictive Analytics Module",
                    "description": "ML-based demand forecasting",
                    "phase_id": p1_phases[1]["id"],
                    "phase_name": p1_phases[1]["name"],
                    "assigned_to": resource_ids[0],  # Sarah
                    "status": "in_progress",
                    "priority": "high",
                    "estimated_hours": 90,
                    "actual_hours": 40,
                    "progress_percentage": 45,
                    "start_date": (today - timedelta(days=10)).isoformat(),
                    "end_date": (today + timedelta(days=25)).isoformat(),
                    "order": 3,
                    "dependencies": [task_ids_p1[0]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[2]
                },
                {
                    "project_id": project_ids[1],
                    "name": "Dashboard UI Development",
                    "description": "Interactive analytics dashboard",
                    "phase_id": p1_phases[1]["id"],
                    "phase_name": p1_phases[1]["name"],
                    "assigned_to": None,
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 80,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=10)).isoformat(),
                    "end_date": (today + timedelta(days=30)).isoformat(),
                    "order": 4,
                    "dependencies": [task_ids_p1[1], task_ids_p1[2]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[3]
                },
                {
                    "project_id": project_ids[1],
                    "name": "API Integration Testing",
                    "description": "Test integrations with warehouse systems",
                    "phase_id": p1_phases[2]["id"],
                    "phase_name": p1_phases[2]["name"],
                    "assigned_to": resource_ids[4],  # Olivia
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 50,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=35)).isoformat(),
                    "end_date": (today + timedelta(days=42)).isoformat(),
                    "order": 5,
                    "dependencies": [task_ids_p1[3]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[4]
                },
                {
                    "project_id": project_ids[1],
                    "name": "Performance Optimization",
                    "description": "Optimize for 10k+ concurrent users",
                    "phase_id": p1_phases[2]["id"],
                    "phase_name": p1_phases[2]["name"],
                    "assigned_to": resource_ids[3],  # James
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 40,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=30)).isoformat(),
                    "end_date": (today + timedelta(days=40)).isoformat(),
                    "order": 6,
                    "dependencies": [task_ids_p1[3]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[5]
                },
                {
                    "project_id": project_ids[1],
                    "name": "Go-Live Deployment",
                    "description": "Production deployment and cutover",
                    "phase_id": p1_phases[2]["id"],
                    "phase_name": p1_phases[2]["name"],
                    "assigned_to": resource_ids[1],  # Michael
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 30,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "is_milestone": True,
                    "milestone_date": (today + timedelta(days=45)).isoformat(),
                    "start_date": (today + timedelta(days=42)).isoformat(),
                    "end_date": (today + timedelta(days=45)).isoformat(),
                    "order": 7,
                    "dependencies": [task_ids_p1[4], task_ids_p1[5]],
                    "demo_seed": True,
                    "_task_id": task_ids_p1[6]
                },
            ])
            
            # --- Brightpath Health Tasks (Project 2) ---
            task_ids_p2 = [str(uuid.uuid4()) for _ in range(6)]
            
            demo_tasks.extend([
                {
                    "project_id": project_ids[2],
                    "name": "Security Requirements Analysis",
                    "description": "HIPAA compliance and security audit",
                    "phase_id": p2_phases[0]["id"],
                    "phase_name": p2_phases[0]["name"],
                    "assigned_to": resource_ids[1],  # Michael
                    "status": "in_progress",
                    "priority": "critical",
                    "estimated_hours": 50,
                    "actual_hours": 20,
                    "progress_percentage": 40,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=15)).isoformat(),
                    "order": 1,
                    "dependencies": [],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[0]
                },
                {
                    "project_id": project_ids[2],
                    "name": "UI/UX Design",
                    "description": "Design patient-friendly portal interface",
                    "phase_id": p2_phases[0]["id"],
                    "phase_name": p2_phases[0]["name"],
                    "assigned_to": resource_ids[2],  # Emma
                    "status": "in_progress",
                    "priority": "high",
                    "estimated_hours": 60,
                    "actual_hours": 15,
                    "progress_percentage": 25,
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=20)).isoformat(),
                    "order": 2,
                    "dependencies": [],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[1]
                },
                {
                    "project_id": project_ids[2],
                    "name": "Authentication System",
                    "description": "Secure login with MFA",
                    "phase_id": p2_phases[1]["id"],
                    "phase_name": p2_phases[1]["name"],
                    "assigned_to": resource_ids[3],  # James
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 70,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=20)).isoformat(),
                    "end_date": (today + timedelta(days=35)).isoformat(),
                    "order": 3,
                    "dependencies": [task_ids_p2[0]],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[2]
                },
                {
                    "project_id": project_ids[2],
                    "name": "Medical Records Integration",
                    "description": "EHR system integration",
                    "phase_id": p2_phases[1]["id"],
                    "phase_name": p2_phases[1]["name"],
                    "assigned_to": resource_ids[3],  # James
                    "status": "todo",
                    "priority": "high",
                    "estimated_hours": 90,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=35)).isoformat(),
                    "end_date": (today + timedelta(days=55)).isoformat(),
                    "order": 4,
                    "dependencies": [task_ids_p2[2]],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[3]
                },
                {
                    "project_id": project_ids[2],
                    "name": "Telehealth Video Module",
                    "description": "WebRTC-based video consultations",
                    "phase_id": p2_phases[1]["id"],
                    "phase_name": p2_phases[1]["name"],
                    "assigned_to": None,
                    "status": "todo",
                    "priority": "medium",
                    "estimated_hours": 80,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "start_date": (today + timedelta(days=40)).isoformat(),
                    "end_date": (today + timedelta(days=65)).isoformat(),
                    "order": 5,
                    "dependencies": [task_ids_p2[2]],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[4]
                },
                {
                    "project_id": project_ids[2],
                    "name": "Security Audit & Launch",
                    "description": "Third-party security audit and go-live",
                    "phase_id": p2_phases[2]["id"],
                    "phase_name": p2_phases[2]["name"],
                    "assigned_to": resource_ids[1],  # Michael
                    "status": "todo",
                    "priority": "critical",
                    "estimated_hours": 50,
                    "actual_hours": 0,
                    "progress_percentage": 0,
                    "is_milestone": True,
                    "milestone_date": (today + timedelta(days=90)).isoformat(),
                    "start_date": (today + timedelta(days=70)).isoformat(),
                    "end_date": (today + timedelta(days=90)).isoformat(),
                    "order": 6,
                    "dependencies": [task_ids_p2[3], task_ids_p2[4]],
                    "demo_seed": True,
                    "_task_id": task_ids_p2[5]
                },
            ])
            
            # Insert tasks and remove internal _task_id field
            for task in demo_tasks:
                task.pop("_task_id", None)  # Remove helper field before insert
                await wbs_tasks_collection.insert_one(task)
                counts["wbs_tasks"] += 1
            
            print(f"✓ Created {counts['wbs_tasks']} WBS tasks")
        except Exception as e:
            print(f"✗ WBS task seeding failed: {e}")
    
    # =================================================================
    # 5. RISKS (2-3 per Active project)
    # =================================================================
    if len(project_ids) >= 3:
        try:
            demo_risks = [
                # Northwind Retail
                {
                    "project_id": project_ids[0],
                    "description": "Payment gateway API rate limits may impact peak traffic performance",
                    "impact": "High",
                    "probability": "Medium",
                    "mitigation": "Implement caching and request throttling; negotiate higher rate limits with provider",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Technical", "Schedule"],
                    "demo_seed": True
                },
                {
                    "project_id": project_ids[0],
                    "description": "Mobile browser compatibility issues requiring extended testing cycles",
                    "impact": "Medium",
                    "probability": "Medium",
                    "mitigation": "Early cross-browser testing; allocate buffer time in schedule",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Technical", "Quality"],
                    "demo_seed": True
                },
                
                # Apex Logistics
                {
                    "project_id": project_ids[1],
                    "description": "Legacy warehouse system integration complexity higher than estimated",
                    "impact": "High",
                    "probability": "High",
                    "mitigation": "Dedicated integration specialist engaged; additional sprint allocated",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Technical", "Schedule", "Budget"],
                    "demo_seed": True
                },
                {
                    "project_id": project_ids[1],
                    "description": "ML model accuracy below acceptable threshold in production environment",
                    "impact": "Medium",
                    "probability": "Low",
                    "mitigation": "Extensive training data collection; fallback to rules-based system",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Technical", "Quality"],
                    "demo_seed": True
                },
                
                # Brightpath Health
                {
                    "project_id": project_ids[2],
                    "description": "HIPAA compliance audit may reveal additional security requirements",
                    "impact": "High",
                    "probability": "Medium",
                    "mitigation": "Engaged HIPAA compliance consultant early; schedule buffer included",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Compliance", "Schedule"],
                    "demo_seed": True
                },
                {
                    "project_id": project_ids[2],
                    "description": "EHR system API documentation incomplete or inaccurate",
                    "impact": "High",
                    "probability": "Medium",
                    "mitigation": "Direct liaison with EHR vendor technical team; prototype integration early",
                    "status": "Active",
                    "category": "Risk",
                    "impact_areas": ["Technical", "Schedule"],
                    "demo_seed": True
                },
            ]
            
            for risk in demo_risks:
                await risks_collection.insert_one(risk)
                counts["risks"] += 1
            
            print(f"✓ Created {counts['risks']} risks")
        except Exception as e:
            print(f"✗ Risk seeding failed: {e}")
    
    # =================================================================
    # 6. STATUS UPDATES (1-2 per Active project with AI summaries)
    # =================================================================
    if len(project_ids) >= 3:
        try:
            demo_status_updates = [
                # Northwind Retail
                {
                    "project_id": project_ids[0],
                    "health": "Green",
                    "schedule_status": "On Track",
                    "actual_progress": 42.0,
                    "accomplishments": "Completed user research phase with 25 customer interviews. Design wireframes 60% complete. Technical architecture approved.",
                    "blockers": "Waiting on final payment gateway API credentials from client IT team.",
                    "next_steps": "Complete mockup designs by end of week. Begin database schema design. Schedule technical review meeting.",
                    "ai_generated_summary": "Project is progressing well with user research completed and design phase on track. Minor delay in payment gateway setup pending client credentials, but not impacting critical path. Team morale is high and stakeholder engagement is excellent.",
                    "progress_summary": "Design phase tracking ahead of schedule. Development phase preparation underway with technical architecture finalized.",
                    "created_at": today - timedelta(days=2),
                    "demo_seed": True
                },
                
                # Apex Logistics
                {
                    "project_id": project_ids[1],
                    "health": "Amber",
                    "schedule_status": "At Risk",
                    "actual_progress": 55.0,
                    "accomplishments": "Real-time tracking engine 70% complete with WebSocket support live. Predictive analytics module showing promising results in testing. Dashboard UI design approved.",
                    "blockers": "Legacy warehouse system integration more complex than originally scoped. API documentation incomplete.",
                    "next_steps": "Escalate warehouse integration issues to client technical team. Complete dashboard UI development. Begin integration testing preparation.",
                    "ai_generated_summary": "Project facing integration challenges with legacy systems causing schedule pressure. Core tracking functionality performing well in tests. Requires management attention on vendor coordination and potential schedule adjustment. Team has proposed mitigation strategies.",
                    "progress_summary": "Core development 55% complete but integration complexity requires additional sprint. Quality of delivered features is high.",
                    "created_at": today - timedelta(days=1),
                    "demo_seed": True
                },
                
                # Brightpath Health
                {
                    "project_id": project_ids[2],
                    "health": "Green",
                    "schedule_status": "On Track",
                    "actual_progress": 15.0,
                    "accomplishments": "Security requirements analysis 40% complete with HIPAA consultant engaged. UI/UX designs 25% complete with positive client feedback. Technical stack approved.",
                    "blockers": "None at this time.",
                    "next_steps": "Complete security requirements documentation. Finalize patient portal UI designs. Begin authentication system planning.",
                    "ai_generated_summary": "Project launched successfully with strong foundation in security and compliance planning. Design work proceeding smoothly with excellent client collaboration. Early engagement of HIPAA specialist reducing risk. All green lights for moving into development phase.",
                    "progress_summary": "Requirements phase on track. Design work progressing with stakeholder approval. Security planning ahead of schedule.",
                    "created_at": today,
                    "demo_seed": True
                },
            ]
            
            for status in demo_status_updates:
                await status_updates_collection.insert_one(status)
                counts["status_updates"] += 1
            
            print(f"✓ Created {counts['status_updates']} status updates")
        except Exception as e:
            print(f"✗ Status update seeding failed: {e}")
    
    # =================================================================
    # 7. TIMESHEETS (for current week, 1-2 resources on 1-2 projects)
    # =================================================================
    if len(resource_ids) >= 2 and len(project_ids) >= 2:
        try:
            # Calculate current week start (Monday)
            week_start = today - timedelta(days=today.weekday())
            
            demo_timesheets = [
                {
                    "resource_id": resource_ids[0],  # Sarah Chen
                    "project_id": project_ids[0],
                    "week_start": week_start,
                    "planned_hours": 32.0,  # 80% allocation
                    "actual_hours": 35.5,
                    "variance": 3.5,
                    "status": "Submitted",
                    "notes": "Extra hours for critical payment gateway work",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[0],  # Sarah Chen
                    "project_id": project_ids[1],
                    "week_start": week_start,
                    "planned_hours": 16.0,  # 40% allocation
                    "actual_hours": 14.0,
                    "variance": -2.0,
                    "status": "Submitted",
                    "notes": "Analytics module refactoring",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[3],  # James Park
                    "project_id": project_ids[1],
                    "week_start": week_start,
                    "planned_hours": 40.0,  # 100% allocation
                    "actual_hours": 42.5,
                    "variance": 2.5,
                    "status": "Submitted",
                    "notes": "Tracking engine optimization and debugging",
                    "demo_seed": True
                },
                {
                    "resource_id": resource_ids[2],  # Emma Rodriguez
                    "project_id": project_ids[0],
                    "week_start": week_start,
                    "planned_hours": 24.0,  # 60% allocation
                    "actual_hours": 26.0,
                    "variance": 2.0,
                    "status": "Submitted",
                    "notes": "Checkout flow wireframes and stakeholder review",
                    "demo_seed": True
                },
            ]
            
            for timesheet in demo_timesheets:
                await timesheets_collection.insert_one(timesheet)
                counts["timesheets"] += 1
            
            print(f"✓ Created {counts['timesheets']} timesheets")
        except Exception as e:
            print(f"✗ Timesheet seeding failed: {e}")
    
    # =================================================================
    # 8. PROPOSALS (1 Confirmed linked to project, 1 Sent)
    # =================================================================
    if len(project_ids) >= 3:
        try:
            # Load v4 sample brief as template
            sample_brief = load_sample_brief()
            
            # --- CONFIRMED Proposal (linked to Brightpath Health) ---
            confirmed_brief = sample_brief.copy()
            confirmed_brief["client_name"] = "Brightpath Health (Demo)"
            confirmed_brief["contact_email"] = "sarah.mitchell@brightpath-demo.test"
            confirmed_brief["proposal_title"] = "Patient Portal Development Proposal"
            confirmed_brief["valid_until"] = (today + timedelta(days=60)).strftime("%B %d, %Y")
            confirmed_brief["challenge_1"] = "Patients struggle with fragmented access to medical records across multiple systems"
            confirmed_brief["challenge_2"] = "Current appointment scheduling process is manual and time-consuming"
            confirmed_brief["challenge_3"] = "No integrated telehealth capability for remote consultations"
            
            confirmed_proposal = {
                "token": secrets.token_urlsafe(32),
                "status": "Confirmed",
                "data": confirmed_brief,
                "created_by": "demo@ddplanner.app",
                "created_at": today - timedelta(days=20),
                "updated_at": today - timedelta(days=5),
                "sent_at": today - timedelta(days=15),
                "valid_until_date": today + timedelta(days=60),
                "accepted_by": "Dr. Sarah Mitchell, Medical Director",
                "accepted_path": "b",
                "accepted_at": today - timedelta(days=10),
                "decline_reason": None,
                "declined_at": None,
                "confirmed_at": today - timedelta(days=5),
                "linked_project_id": project_ids[2],  # Brightpath Health
                "linked_client_user_id": None,
                "linked_report_token": None,
                "last_client_activity_at": today - timedelta(days=5),
                "demo_seed": True
            }
            
            await proposals_collection.insert_one(confirmed_proposal)
            counts["proposals"] += 1
            
            # --- SENT Proposal (not yet accepted) ---
            sent_brief = sample_brief.copy()
            sent_brief["client_name"] = "Summit Insurance Group"
            sent_brief["contact_email"] = "patricia.wong@summitins-demo.test"
            sent_brief["proposal_title"] = "Claims Processing Automation"
            sent_brief["valid_until"] = (today + timedelta(days=30)).strftime("%B %d, %Y")
            sent_brief["challenge_1"] = "Manual claims processing causing 5-7 day turnaround times"
            sent_brief["challenge_2"] = "High error rate in claims data entry (15% requiring rework)"
            sent_brief["challenge_3"] = "Limited visibility into claims pipeline and bottlenecks"
            
            sent_proposal = {
                "token": secrets.token_urlsafe(32),
                "status": "Viewed",
                "data": sent_brief,
                "created_by": "demo@ddplanner.app",
                "created_at": today - timedelta(days=7),
                "updated_at": today - timedelta(days=3),
                "sent_at": today - timedelta(days=5),
                "valid_until_date": today + timedelta(days=30),
                "accepted_by": None,
                "accepted_path": None,
                "accepted_at": None,
                "decline_reason": None,
                "declined_at": None,
                "confirmed_at": None,
                "linked_project_id": None,
                "linked_client_user_id": None,
                "linked_report_token": None,
                "last_client_activity_at": today - timedelta(days=2),
                "interested_path": "a",  # Client showed interest in path A
                "demo_seed": True
            }
            
            await proposals_collection.insert_one(sent_proposal)
            counts["proposals"] += 1
            
            print(f"✓ Created {counts['proposals']} proposals")
        except Exception as e:
            print(f"✗ Proposal seeding failed: {e}")
    
    # =================================================================
    # 9. REPORT LINKS (1 linked to Brightpath Health project)
    # =================================================================
    if len(project_ids) >= 3:
        try:
            report_link_doc = {
                "token": secrets.token_urlsafe(64),
                "project_id": project_ids[2],  # Brightpath Health
                "report_type": "project_status",
                "report_period": "whole_project",
                "created_at": (today - timedelta(days=5)).isoformat(),
                "expires_at": (today + timedelta(days=25)).isoformat(),
                "recipient_email": "sarah.mitchell@brightpath-demo.test",
                "verification_code": str(123456),  # Demo code
                "is_active": True,
                "view_count": 3,
                "last_viewed_at": (today - timedelta(days=1)).isoformat(),
                "verified_at": (today - timedelta(days=4)).isoformat(),
                "demo_seed": True
            }
            
            await report_links_collection.insert_one(report_link_doc)
            counts["report_links"] += 1
            
            print(f"✓ Created {counts['report_links']} report link")
        except Exception as e:
            print(f"✗ Report link seeding failed: {e}")
    
    # =================================================================
    # SUMMARY
    # =================================================================
    print("\n" + "=" * 60)
    print("✅ DEMO DATASET SEEDED SUCCESSFULLY")
    print("=" * 60)
    print(f"Resources:       {counts['resources']}")
    print(f"Projects:        {counts['projects']}")
    print(f"Allocations:     {counts['allocations']}")
    print(f"WBS Tasks:       {counts['wbs_tasks']}")
    print(f"Risks:           {counts['risks']}")
    print(f"Status Updates:  {counts['status_updates']}")
    print(f"Timesheets:      {counts['timesheets']}")
    print(f"Holidays:        {counts['holidays']}")
    print(f"Proposals:       {counts['proposals']}")
    print(f"Report Links:    {counts['report_links']}")
    print("=" * 60)
    print("All data tagged with: demo_seed=True")
    print("=" * 60)
    
    return {
        "status": "success",
        "message": "Demo dataset seeded successfully",
        "counts": counts
    }

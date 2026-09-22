"""
Test script for ReportLab PDF export.
"""
import sys
from datetime import date
from services.exports.reportlab_export import build_project_pdf_reportlab


def test_basic_pdf():
    """Test basic PDF generation with sample data."""
    
    # Sample project data
    project = {
        'name': 'Digital Transformation Initiative',
        'client_name': 'Acme Corporation',
        'status': 'Active',
        'health': 'Green',
        'start_date': date(2025, 1, 15),
        'end_date': date(2025, 6, 30),
        'budgeted_hours': 2400,
        'team_load': 87,
        'executive_summary': 'This project aims to modernize Acme Corporation\'s legacy systems through a comprehensive digital transformation strategy. The initiative includes cloud migration, process automation, and enhanced data analytics capabilities.',
        'project_objective': 'Transform Acme\'s operations by implementing modern cloud infrastructure, automating manual processes, and establishing data-driven decision-making frameworks to improve efficiency by 40% and reduce operational costs by $2M annually.',
    }
    
    # Sample allocations
    allocations = [
        {
            'resource_name': 'John Smith',
            'role': 'Project Manager',
            'allocation_percent': 100
        },
        {
            'resource_name': 'Sarah Johnson',
            'role': 'Senior Developer',
            'allocation_percent': 80
        },
        {
            'resource_name': 'Mike Davis',
            'role': 'DevOps Engineer',
            'allocation_percent': 60
        },
        {
            'resource_name': 'Emily Chen',
            'role': 'UX Designer',
            'allocation_percent': 50
        },
    ]
    
    # Sample risks
    risks = [
        {
            'description': 'Legacy system integration complexity may cause delays',
            'impact': 'High',
            'probability': 'Medium',
            'status': 'Active'
        },
        {
            'description': 'Resource availability during peak holiday season',
            'impact': 'Medium',
            'probability': 'High',
            'status': 'Monitoring'
        },
        {
            'description': 'Third-party API changes could impact integration timeline',
            'impact': 'Low',
            'probability': 'Low',
            'status': 'Active'
        },
    ]
    
    # Sample status updates
    status_updates = [
        {
            'accomplishments': 'Completed cloud infrastructure setup, migrated 60% of legacy systems, implemented automated CI/CD pipeline, conducted user training sessions for 50+ employees.',
            'next_steps': 'Complete remaining legacy system migrations, conduct security audit, finalize data analytics dashboard, prepare for user acceptance testing phase.',
        }
    ]
    
    print("Generating PDF with sample data...")
    pdf_bytes = build_project_pdf_reportlab(
        project=project,
        risks=risks,
        allocations=allocations,
        status_updates=status_updates
    )
    
    print(f"✓ PDF generated successfully: {len(pdf_bytes)} bytes")
    
    # Save to file for inspection
    output_path = '/app/backend/test_project_report.pdf'
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"✓ PDF saved to: {output_path}")
    return True


def test_minimal_pdf():
    """Test PDF generation with minimal data."""
    
    project = {
        'name': 'Minimal Project',
        'client_name': 'Test Client',
        'status': 'Pipeline',
    }
    
    print("\nGenerating PDF with minimal data...")
    pdf_bytes = build_project_pdf_reportlab(project=project)
    
    print(f"✓ Minimal PDF generated successfully: {len(pdf_bytes)} bytes")
    
    output_path = '/app/backend/test_minimal_report.pdf'
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"✓ Minimal PDF saved to: {output_path}")
    return True


def test_error_handling():
    """Test error handling with invalid data."""
    
    # Test with None values
    project = {
        'name': None,
        'client_name': None,
        'status': None,
        'invalid_key': 'should_not_crash',
    }
    
    print("\nTesting error handling with invalid data...")
    pdf_bytes = build_project_pdf_reportlab(project=project)
    
    print(f"✓ Error handling test passed: {len(pdf_bytes)} bytes")
    
    output_path = '/app/backend/test_error_handling.pdf'
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    
    print(f"✓ Error handling PDF saved to: {output_path}")
    return True


if __name__ == '__main__':
    try:
        print("=" * 60)
        print("Testing ReportLab PDF Export")
        print("=" * 60)
        
        # Run tests
        test_basic_pdf()
        test_minimal_pdf()
        test_error_handling()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

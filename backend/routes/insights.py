"""
Insights & Predictive Analytics API Routes
===========================================
Provides health scoring, predictions, and AI-generated portfolio insights.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
import logging

from auth.dependencies import get_current_user, require_admin
from services.insights import (
    compute_health_score,
    predict_completion,
    get_portfolio_health_scores
)
from services.ai_providers import call_emergent_fallback
from database import projects_collection

router = APIRouter(prefix="/api/insights", tags=["insights"])
logger = logging.getLogger(__name__)


@router.get("/project/{project_id}/health-score")
async def get_project_health_score(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get health score for a single project.
    Returns composite health score with dimensional breakdown.
    """
    try:
        health_score = await compute_health_score(project_id)
        return health_score
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting health score for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute health score")


@router.get("/portfolio/health-scores")
async def get_portfolio_health(
    current_user: dict = Depends(get_current_user)
):
    """
    Get health scores for ALL active projects.
    Returns list of health scores sorted by risk (lowest scores first).
    """
    try:
        health_scores = await get_portfolio_health_scores()
        return {
            "projects": health_scores,
            "total_count": len(health_scores),
            "summary": {
                "grade_a": sum(1 for p in health_scores if p["grade"] == "A"),
                "grade_b": sum(1 for p in health_scores if p["grade"] == "B"),
                "grade_c": sum(1 for p in health_scores if p["grade"] == "C"),
                "grade_d": sum(1 for p in health_scores if p["grade"] == "D"),
                "grade_f": sum(1 for p in health_scores if p["grade"] == "F"),
                "average_score": round(sum(p["overall_score"] for p in health_scores) / len(health_scores), 1) if health_scores else 0
            }
        }
    except Exception as e:
        logger.error(f"Error getting portfolio health scores: {e}")
        raise HTTPException(status_code=500, detail="Failed to get portfolio health scores")


@router.get("/project/{project_id}/predictions")
async def get_project_predictions(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get predictive analytics for a project.
    Returns completion date prediction, velocity, and budget forecast.
    """
    try:
        predictions = await predict_completion(project_id)
        return predictions
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting predictions for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute predictions")


@router.get("/weekly-digest")
async def get_weekly_digest(
    current_user: dict = Depends(require_admin)
):
    """
    AI-generated weekly portfolio digest.
    Uses AI to generate a narrative summary from health scores and predictions.
    Admin access required.
    """
    try:
        # Get portfolio health scores
        health_scores = await get_portfolio_health_scores()
        
        if not health_scores:
            return {
                "executive_summary": "No active projects to report on.",
                "highlights": [],
                "alerts": [],
                "recommendations": [],
                "portfolio_health": "healthy"
            }
        
        # Get predictions for all projects
        predictions = []
        for project in health_scores:
            try:
                pred = await predict_completion(project["project_id"])
                pred["project_name"] = project.get("project_name")
                predictions.append(pred)
            except Exception:
                continue
        
        # Prepare data for AI
        portfolio_summary = {
            "total_projects": len(health_scores),
            "average_score": round(sum(p["overall_score"] for p in health_scores) / len(health_scores), 1),
            "grade_distribution": {
                "A": sum(1 for p in health_scores if p["grade"] == "A"),
                "B": sum(1 for p in health_scores if p["grade"] == "B"),
                "C": sum(1 for p in health_scores if p["grade"] == "C"),
                "D": sum(1 for p in health_scores if p["grade"] == "D"),
                "F": sum(1 for p in health_scores if p["grade"] == "F")
            },
            "at_risk_projects": [
                {
                    "name": p.get("project_name"),
                    "client": p.get("client_name"),
                    "score": p["overall_score"],
                    "grade": p["grade"],
                    "dimensions": p["dimensions"]
                }
                for p in health_scores if p["overall_score"] < 70
            ],
            "top_performers": [
                {
                    "name": p.get("project_name"),
                    "client": p.get("client_name"),
                    "score": p["overall_score"],
                    "grade": p["grade"]
                }
                for p in sorted(health_scores, key=lambda x: x["overall_score"], reverse=True)[:3]
            ],
            "predictions": [
                {
                    "name": pred.get("project_name"),
                    "status": pred["status"],
                    "variance_days": pred["variance_days"],
                    "will_exceed_budget": pred["budget_prediction"].get("will_exceed_budget", False)
                }
                for pred in predictions if pred["status"] in ["at_risk", "critical"]
            ]
        }
        
        # Construct AI prompt
        system_prompt = """You are a senior project portfolio analyst. Generate a concise weekly digest based on the portfolio data provided.

Be direct, data-driven, and actionable. Focus on what matters most: risks, opportunities, and specific recommendations.

Return your analysis as a JSON object with exactly these fields:
{
  "executive_summary": "2-3 sentence overview of portfolio health and key trends",
  "highlights": [{"project": "project name", "insight": "one sentence positive insight"}],
  "alerts": [{"severity": "high|medium|low", "message": "specific issue and impact"}],
  "recommendations": [{"priority": "high|medium|low", "action": "specific actionable recommendation"}],
  "portfolio_health": "healthy|needs_attention|at_risk"
}"""
        
        user_message = f"""Analyze this project portfolio and generate a weekly digest:

PORTFOLIO SUMMARY:
- Total Active Projects: {portfolio_summary['total_projects']}
- Average Health Score: {portfolio_summary['average_score']}/100
- Grade Distribution: {portfolio_summary['grade_distribution']}

AT-RISK PROJECTS ({len(portfolio_summary['at_risk_projects'])}):
{chr(10).join([f"- {p['name']} ({p['client']}): Score {p['score']}/100 (Grade {p['grade']})" for p in portfolio_summary['at_risk_projects']])}

TOP PERFORMERS:
{chr(10).join([f"- {p['name']} ({p['client']}): Score {p['score']}/100 (Grade {p['grade']})" for p in portfolio_summary['top_performers']])}

SCHEDULE CONCERNS:
{chr(10).join([f"- {p['name']}: {p['status']} ({p['variance_days']} days variance)" for p in portfolio_summary['predictions'] if p['status'] in ['at_risk', 'critical']])}

BUDGET CONCERNS:
{chr(10).join([f"- {p['name']}: Budget overrun predicted" for p in portfolio_summary['predictions'] if p.get('will_exceed_budget')])}

Generate the weekly digest JSON now."""
        
        # Call AI
        try:
            digest = await call_emergent_fallback(system_prompt, user_message)
            
            if digest and isinstance(digest, dict):
                return digest
            else:
                # Fallback if AI fails
                logger.warning("AI digest generation failed, returning basic summary")
                return _generate_fallback_digest(portfolio_summary)
                
        except Exception as ai_error:
            logger.error(f"AI error generating digest: {ai_error}")
            return _generate_fallback_digest(portfolio_summary)
        
    except Exception as e:
        logger.error(f"Error generating weekly digest: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate weekly digest")


@router.get("/portfolio/trends")
async def get_portfolio_trends(
    current_user: dict = Depends(get_current_user)
):
    """
    Get portfolio trend data (health scores over time).
    Currently returns current scores with trend indicators.
    Future: Will include historical data.
    """
    try:
        health_scores = await get_portfolio_health_scores()
        
        # For now, return current scores with trend field
        # Future enhancement: query historical health scores from a trends collection
        return {
            "projects": health_scores,
            "trend_period": "current",
            "note": "Historical trend tracking coming soon"
        }
        
    except Exception as e:
        logger.error(f"Error getting portfolio trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get portfolio trends")


def _generate_fallback_digest(portfolio_summary: dict) -> dict:
    """Generate a basic digest when AI is unavailable."""
    avg_score = portfolio_summary['average_score']
    at_risk_count = len(portfolio_summary['at_risk_projects'])
    
    if avg_score >= 80:
        portfolio_health = "healthy"
        summary = f"Portfolio is healthy with {portfolio_summary['total_projects']} active projects averaging {avg_score}/100."
    elif avg_score >= 65:
        portfolio_health = "needs_attention"
        summary = f"Portfolio needs attention with {at_risk_count} projects below target performance."
    else:
        portfolio_health = "at_risk"
        summary = f"Portfolio health is at risk with average score of {avg_score}/100 and {at_risk_count} struggling projects."
    
    alerts = []
    for project in portfolio_summary['at_risk_projects']:
        severity = "high" if project['score'] < 50 else "medium"
        alerts.append({
            "severity": severity,
            "message": f"{project['name']} ({project['client']}) has health score of {project['score']}/100"
        })
    
    recommendations = []
    if at_risk_count > 0:
        recommendations.append({
            "priority": "high",
            "action": f"Review and address issues in {at_risk_count} at-risk projects"
        })
    
    highlights = [
        {
            "project": p['name'],
            "insight": f"Excellent performance with {p['score']}/100 health score"
        }
        for p in portfolio_summary['top_performers'][:2] if p['score'] >= 85
    ]
    
    return {
        "executive_summary": summary,
        "highlights": highlights,
        "alerts": alerts,
        "recommendations": recommendations,
        "portfolio_health": portfolio_health
    }

"""
Analytics Module for Moodometer

Provides statistical analysis and insights for mood data.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import MoodModel, UserModel
import statistics


def calculate_mood_statistics(
    db: Session,
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict:
    """
    Calculate comprehensive mood statistics for a user.
    
    Args:
        db: Database session
        user_id: User ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        
    Returns:
        Dictionary containing mood statistics
    """
    # Build query
    query = db.query(MoodModel).filter(MoodModel.user_id == user_id)
    
    if start_date:
        query = query.filter(MoodModel.timestamp >= start_date)
    if end_date:
        query = query.filter(MoodModel.timestamp <= end_date)
    
    moods = query.all()
    
    if not moods:
        return {
            "total_entries": 0,
            "date_range": None,
            "statistics": None
        }
    
    # Extract energy and valence values
    energy_values = [mood.energy for mood in moods]
    valence_values = [mood.valence for mood in moods]
    
    # Calculate statistics
    stats = {
        "total_entries": len(moods),
        "date_range": {
            "start": min(mood.timestamp for mood in moods).isoformat(),
            "end": max(mood.timestamp for mood in moods).isoformat()
        },
        "energy": {
            "mean": statistics.mean(energy_values),
            "median": statistics.median(energy_values),
            "stdev": statistics.stdev(energy_values) if len(energy_values) > 1 else 0,
            "min": min(energy_values),
            "max": max(energy_values)
        },
        "valence": {
            "mean": statistics.mean(valence_values),
            "median": statistics.median(valence_values),
            "stdev": statistics.stdev(valence_values) if len(valence_values) > 1 else 0,
            "min": min(valence_values),
            "max": max(valence_values)
        },
        "quadrant_distribution": calculate_quadrant_distribution(moods),
        "trends": calculate_trends(moods),
        "most_common_mood": get_most_common_mood(moods)
    }
    
    return stats


def calculate_quadrant_distribution(moods: List[MoodModel]) -> Dict[str, int]:
    """
    Calculate the distribution of moods across emotional quadrants.
    
    Args:
        moods: List of mood entries
        
    Returns:
        Dictionary with quadrant names and counts
    """
    quadrants = {
        "high_energy_pleasant": 0,      # Top right
        "high_energy_unpleasant": 0,    # Top left
        "low_energy_pleasant": 0,       # Bottom right
        "low_energy_unpleasant": 0,     # Bottom left
        "neutral": 0
    }
    
    for mood in moods:
        if abs(mood.energy) < 0.1 and abs(mood.valence) < 0.1:
            quadrants["neutral"] += 1
        elif mood.energy > 0 and mood.valence > 0:
            quadrants["high_energy_pleasant"] += 1
        elif mood.energy > 0 and mood.valence < 0:
            quadrants["high_energy_unpleasant"] += 1
        elif mood.energy < 0 and mood.valence > 0:
            quadrants["low_energy_pleasant"] += 1
        else:
            quadrants["low_energy_unpleasant"] += 1
    
    # Calculate percentages
    total = len(moods)
    quadrants_pct = {
        k: {"count": v, "percentage": round((v / total) * 100, 2)}
        for k, v in quadrants.items()
    }
    
    return quadrants_pct


def calculate_trends(moods: List[MoodModel]) -> Dict:
    """
    Calculate mood trends over time.
    
    Args:
        moods: List of mood entries (should be sorted by timestamp)
        
    Returns:
        Dictionary with trend information
    """
    if len(moods) < 2:
        return {
            "energy_trend": "insufficient_data",
            "valence_trend": "insufficient_data",
            "overall_trend": "insufficient_data"
        }
    
    # Sort by timestamp
    sorted_moods = sorted(moods, key=lambda m: m.timestamp)
    
    # Split into first and second half
    mid = len(sorted_moods) // 2
    first_half = sorted_moods[:mid]
    second_half = sorted_moods[mid:]
    
    # Calculate averages for each half
    first_energy_avg = statistics.mean([m.energy for m in first_half])
    second_energy_avg = statistics.mean([m.energy for m in second_half])
    
    first_valence_avg = statistics.mean([m.valence for m in first_half])
    second_valence_avg = statistics.mean([m.valence for m in second_half])
    
    # Determine trends
    energy_diff = second_energy_avg - first_energy_avg
    valence_diff = second_valence_avg - first_valence_avg
    
    def get_trend_direction(diff: float, threshold: float = 0.1) -> str:
        if abs(diff) < threshold:
            return "stable"
        return "increasing" if diff > 0 else "decreasing"
    
    energy_trend = get_trend_direction(energy_diff)
    valence_trend = get_trend_direction(valence_diff)
    
    # Overall trend interpretation
    if energy_trend == "increasing" and valence_trend == "increasing":
        overall = "improving"
    elif energy_trend == "decreasing" and valence_trend == "decreasing":
        overall = "declining"
    elif energy_trend == "stable" and valence_trend == "stable":
        overall = "stable"
    else:
        overall = "mixed"
    
    return {
        "energy_trend": energy_trend,
        "energy_change": round(energy_diff, 3),
        "valence_trend": valence_trend,
        "valence_change": round(valence_diff, 3),
        "overall_trend": overall
    }


def get_most_common_mood(moods: List[MoodModel]) -> Dict:
    """
    Identify the most common mood quadrant.
    
    Args:
        moods: List of mood entries
        
    Returns:
        Dictionary with most common mood information
    """
    quadrant_counts = {}
    
    for mood in moods:
        quadrant = get_mood_quadrant_name(mood.energy, mood.valence)
        quadrant_counts[quadrant] = quadrant_counts.get(quadrant, 0) + 1
    
    if not quadrant_counts:
        return {"quadrant": "none", "count": 0, "percentage": 0}
    
    most_common = max(quadrant_counts.items(), key=lambda x: x[1])
    
    return {
        "quadrant": most_common[0],
        "count": most_common[1],
        "percentage": round((most_common[1] / len(moods)) * 100, 2)
    }


def get_mood_quadrant_name(energy: float, valence: float) -> str:
    """
    Get the quadrant name for given energy/valence values.
    
    Args:
        energy: Energy level (-1 to 1)
        valence: Valence level (-1 to 1)
        
    Returns:
        Quadrant name string
    """
    if abs(energy) < 0.1 and abs(valence) < 0.1:
        return "neutral"
    elif energy > 0 and valence > 0:
        return "high_energy_pleasant"
    elif energy > 0 and valence < 0:
        return "high_energy_unpleasant"
    elif energy < 0 and valence > 0:
        return "low_energy_pleasant"
    else:
        return "low_energy_unpleasant"


def detect_mood_patterns(
    db: Session,
    user_id: int,
    days: int = 30
) -> Dict:
    """
    Detect patterns in mood data over a specified period.
    
    Args:
        db: Database session
        user_id: User ID
        days: Number of days to analyze
        
    Returns:
        Dictionary with detected patterns
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    moods = db.query(MoodModel).filter(
        MoodModel.user_id == user_id,
        MoodModel.timestamp >= start_date,
        MoodModel.timestamp <= end_date
    ).order_by(MoodModel.timestamp).all()
    
    if len(moods) < 7:
        return {
            "patterns_detected": False,
            "message": "Insufficient data for pattern detection (minimum 7 entries required)"
        }
    
    patterns = {
        "patterns_detected": True,
        "time_of_day": analyze_time_of_day_patterns(moods),
        "day_of_week": analyze_day_of_week_patterns(moods),
        "volatility": calculate_mood_volatility(moods),
        "streaks": detect_mood_streaks(moods)
    }
    
    return patterns


def analyze_time_of_day_patterns(moods: List[MoodModel]) -> Dict:
    """Analyze mood patterns by time of day."""
    time_buckets = {
        "morning": [],    # 6-12
        "afternoon": [],  # 12-18
        "evening": [],    # 18-24
        "night": []       # 0-6
    }
    
    for mood in moods:
        hour = mood.timestamp.hour
        if 6 <= hour < 12:
            bucket = "morning"
        elif 12 <= hour < 18:
            bucket = "afternoon"
        elif 18 <= hour < 24:
            bucket = "evening"
        else:
            bucket = "night"
        
        time_buckets[bucket].append((mood.energy, mood.valence))
    
    # Calculate averages for each time bucket
    result = {}
    for time_period, values in time_buckets.items():
        if values:
            avg_energy = statistics.mean([v[0] for v in values])
            avg_valence = statistics.mean([v[1] for v in values])
            result[time_period] = {
                "count": len(values),
                "avg_energy": round(avg_energy, 3),
                "avg_valence": round(avg_valence, 3)
            }
    
    return result


def analyze_day_of_week_patterns(moods: List[MoodModel]) -> Dict:
    """Analyze mood patterns by day of week."""
    day_buckets = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
    
    for mood in moods:
        day = mood.timestamp.weekday()
        day_buckets[day].append((mood.energy, mood.valence))
    
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result = {}
    
    for day_num, values in day_buckets.items():
        if values:
            avg_energy = statistics.mean([v[0] for v in values])
            avg_valence = statistics.mean([v[1] for v in values])
            result[day_names[day_num]] = {
                "count": len(values),
                "avg_energy": round(avg_energy, 3),
                "avg_valence": round(avg_valence, 3)
            }
    
    return result


def calculate_mood_volatility(moods: List[MoodModel]) -> Dict:
    """Calculate mood volatility (how much moods fluctuate)."""
    if len(moods) < 2:
        return {"volatility": "insufficient_data"}
    
    energy_values = [m.energy for m in moods]
    valence_values = [m.valence for m in moods]
    
    energy_stdev = statistics.stdev(energy_values)
    valence_stdev = statistics.stdev(valence_values)
    
    # Combined volatility score
    volatility_score = (energy_stdev + valence_stdev) / 2
    
    # Classify volatility
    if volatility_score < 0.3:
        classification = "low"
    elif volatility_score < 0.6:
        classification = "moderate"
    else:
        classification = "high"
    
    return {
        "volatility_score": round(volatility_score, 3),
        "classification": classification,
        "energy_volatility": round(energy_stdev, 3),
        "valence_volatility": round(valence_stdev, 3)
    }


def detect_mood_streaks(moods: List[MoodModel]) -> Dict:
    """Detect consecutive periods of similar moods."""
    if len(moods) < 2:
        return {"streaks": []}
    
    sorted_moods = sorted(moods, key=lambda m: m.timestamp)
    streaks = []
    current_streak = {
        "quadrant": get_mood_quadrant_name(sorted_moods[0].energy, sorted_moods[0].valence),
        "start": sorted_moods[0].timestamp,
        "count": 1
    }
    
    for i in range(1, len(sorted_moods)):
        mood = sorted_moods[i]
        quadrant = get_mood_quadrant_name(mood.energy, mood.valence)
        
        if quadrant == current_streak["quadrant"]:
            current_streak["count"] += 1
        else:
            if current_streak["count"] >= 3:  # Only record streaks of 3+
                current_streak["end"] = sorted_moods[i-1].timestamp
                streaks.append(current_streak.copy())
            
            current_streak = {
                "quadrant": quadrant,
                "start": mood.timestamp,
                "count": 1
            }
    
    # Check final streak
    if current_streak["count"] >= 3:
        current_streak["end"] = sorted_moods[-1].timestamp
        streaks.append(current_streak)
    
    return {
        "total_streaks": len(streaks),
        "streaks": [
            {
                "quadrant": s["quadrant"],
                "duration_entries": s["count"],
                "start_date": s["start"].isoformat(),
                "end_date": s["end"].isoformat()
            }
            for s in streaks
        ]
    }


def generate_insights(
    db: Session,
    user_id: int
) -> List[str]:
    """
    Generate human-readable insights from mood data.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        List of insight strings
    """
    insights = []
    
    # Get statistics
    stats = calculate_mood_statistics(db, user_id)
    
    if stats["total_entries"] == 0:
        return ["Start tracking your moods to get personalized insights!"]
    
    if stats["total_entries"] < 7:
        insights.append(f"You have {stats['total_entries']} mood entries. Track more moods to unlock deeper insights!")
        return insights
    
    # Energy insights
    avg_energy = stats["energy"]["mean"]
    if avg_energy > 0.3:
        insights.append("💪 You generally have high energy levels!")
    elif avg_energy < -0.3:
        insights.append("😴 Your energy levels tend to be low. Consider activities that boost your energy.")
    else:
        insights.append("⚖️ Your energy levels are balanced.")
    
    # Valence insights
    avg_valence = stats["valence"]["mean"]
    if avg_valence > 0.3:
        insights.append("😊 You're experiencing mostly pleasant emotions!")
    elif avg_valence < -0.3:
        insights.append("😔 You've been experiencing challenging emotions. Consider reaching out for support.")
    else:
        insights.append("😐 Your emotional valence is neutral.")
    
    # Trend insights
    trends = stats["trends"]
    if trends["overall_trend"] == "improving":
        insights.append("📈 Great news! Your mood is trending upward!")
    elif trends["overall_trend"] == "declining":
        insights.append("📉 Your mood has been declining. This might be a good time to practice self-care.")
    
    # Most common mood
    most_common = stats["most_common_mood"]
    if most_common["percentage"] > 40:
        insights.append(f"🎯 You spend {most_common['percentage']}% of your time in the {most_common['quadrant'].replace('_', ' ')} state.")
    
    # Patterns
    patterns = detect_mood_patterns(db, user_id, days=30)
    if patterns.get("patterns_detected"):
        volatility = patterns["volatility"]
        if volatility["classification"] == "high":
            insights.append("🎢 Your moods fluctuate significantly. Consider tracking what triggers these changes.")
        elif volatility["classification"] == "low":
            insights.append("🎯 Your moods are quite stable!")
    
    return insights

# Made with Bob

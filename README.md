# Trending Dropshipping Niches Analyzer

A Python script that analyzes trending dropshipping niches using Google Trends data. The script identifies "Green Light" niches with steady growth and low volatility, helping you make data-driven decisions for your dropshipping business.

## Features

- **Google Trends Analysis**: Fetches 12 months of trend data for multiple niches
- **Volatility vs Growth Scoring**: Calculates a ratio to identify stable, growing niches
- **Stability Analysis**: Detects significant dips in interest trends
- **Visualization**: Creates matplotlib graphs showing trajectory trends
- **Green Light Filtering**: Identifies niches with steady growth without huge dips

## Installation

1. Install Python 3.7 or higher
2. Install required packages:

```bash
pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python trending_niches_analyzer.py
```

The script will:
1. Analyze 8 trending dropshipping niches based on 2025-2026 research
2. Calculate growth, volatility, and stability metrics for each niche
3. Generate two visualization graphs:
   - `combined_trajectories.png`: All niches on one graph for comparison
   - `niche_trajectories.png`: Individual subplots for each niche
4. Print a list of "Green Light" niches that meet the criteria

## Niches Analyzed

The script analyzes the following niches:

- Kitchen Gadgets
- Eco-Friendly Products
- Pet Supplies
- Health & Wellness
- Smart Home Gadgets
- Beauty & Skincare
- Outdoor & Camping
- Phone Accessories

Each niche is analyzed using 5 relevant keywords to get a comprehensive view.

## Metrics Explained

- **Growth**: Percentage increase in interest from start to end of the 12-month period
- **Volatility**: Coefficient of variation (normalized standard deviation) showing how much the interest fluctuates
- **Volatility/Growth Ratio**: Lower is better - indicates less volatility relative to growth
- **Stability Score**: 0-1 score indicating how stable the trend is (fewer dips = higher score)

## Green Light Criteria

A niche is considered "Green Light" if it meets all of these criteria:
- Growth ≥ 5%
- Volatility/Growth Ratio ≤ 2.0
- Stability Score ≥ 0.6

You can adjust these thresholds in the `identify_green_light_niches()` method call in `main()`.

## Rate Limiting

The script includes rate limiting to avoid being blocked by Google Trends. The analysis may take several minutes to complete.

## Notes

- Google Trends data is normalized (0-100 scale)
- Results may vary based on geographic location and time of day
- The script uses a 12-month timeframe for analysis
- Multiple keywords per niche provide more robust analysis

## Customization

You can customize the script by:
- Adding/removing niches in `get_trending_niches()`
- Adjusting keywords for each niche
- Modifying the Green Light criteria thresholds
- Changing the timeframe (currently 'today 12-m')

## License

This script is provided as-is for educational and business analysis purposes.


#!/usr/bin/env python3
"""
Trending Dropshipping Niches Analyzer

This script analyzes trending dropshipping niches using Google Trends data.
It calculates volatility vs growth ratios and identifies "Green Light" niches
with steady growth without significant dips.
"""

import matplotlib.pyplot as plt
import numpy as np
from pytrends.request import TrendReq
from datetime import datetime
import time
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class NichesAnalyzer:
    """Analyzes dropshipping niches using Google Trends data."""
    
    def __init__(self, hl='en-US', tz=360):
        """Initialize the analyzer with pytrends."""
        self.pytrends = TrendReq(hl=hl, tz=tz)
        self.results = {}
        
    def get_trending_niches(self) -> Dict[str, List[str]]:
        """
        Returns a dictionary of trending niches and their associated keywords.
        Based on 2025-2026 trending dropshipping niches research.
        """
        return {
            'Kitchen Gadgets': [
                'air fryer accessories',
                'meal prep containers',
                'silicone baking mats',
                'kitchen gadgets',
                'portable blender'
            ],
            'Eco-Friendly Products': [
                'bamboo toothbrush',
                'reusable water bottle',
                'eco friendly products',
                'sustainable products',
                'reusable bags'
            ],
            'Pet Supplies': [
                'pet beds',
                'dog toys',
                'pet accessories',
                'cat furniture',
                'pet grooming'
            ],
            'Health & Wellness': [
                'fitness tracker',
                'posture corrector',
                'yoga mat',
                'resistance bands',
                'massage gun'
            ],
            'Smart Home Gadgets': [
                'smart LED lights',
                'smart home devices',
                'wireless charger',
                'smart plugs',
                'home automation'
            ],
            'Beauty & Skincare': [
                'skincare devices',
                'LED face mask',
                'beauty tools',
                'skincare routine',
                'anti-aging devices'
            ],
            'Outdoor & Camping': [
                'camping gear',
                'portable power bank',
                'outdoor accessories',
                'hiking gear',
                'camping equipment'
            ],
            'Phone Accessories': [
                'phone case',
                'phone stand',
                'wireless earbuds',
                'phone accessories',
                'screen protector'
            ]
        }
    
    def fetch_trends_data(self, keywords: List[str], timeframe: str = 'today 12-m'):
        """
        Fetch Google Trends data for a list of keywords.
        Returns DataFrame with timestamps as index.
        """
        try:
            # Build payload - pytrends can handle up to 5 keywords at once
            if len(keywords) > 5:
                keywords = keywords[:5]  # Limit to 5 keywords per request
                
            self.pytrends.build_payload(
                keywords,
                cat=0,
                timeframe=timeframe,
                geo='',
                gprop=''
            )
            
            # Get interest over time
            data = self.pytrends.interest_over_time()
            
            if data.empty:
                return None
            
            # Remove isPartial column if present
            if 'isPartial' in data.columns:
                data = data.drop(columns=['isPartial'])
            
            # Rate limiting to avoid being blocked
            time.sleep(1)
            
            return data
            
        except Exception as e:
            print(f"Error fetching data for {keywords}: {e}")
            return None
    
    def calculate_growth(self, values: np.ndarray) -> float:
        """
        Calculate percentage growth from start to end.
        Uses average of first and last periods to smooth out noise.
        """
        if len(values) < 2:
            return 0.0
        
        # Use average of first 3 values vs last 3 values for more stable calculation
        start_avg = np.mean(values[:min(3, len(values))])
        end_avg = np.mean(values[-min(3, len(values)):])
        
        if start_avg == 0:
            return 0.0 if end_avg == 0 else 100.0
        
        return ((end_avg - start_avg) / start_avg) * 100
    
    def calculate_volatility(self, values: np.ndarray) -> float:
        """
        Calculate volatility as coefficient of variation (CV).
        This normalizes volatility relative to the mean.
        """
        if len(values) < 2:
            return 0.0
        
        mean_val = np.mean(values)
        if mean_val == 0:
            return 0.0
        
        std_val = np.std(values)
        return (std_val / mean_val) * 100  # Coefficient of variation as percentage
    
    def calculate_trend_stability(self, values: np.ndarray) -> float:
        """
        Calculate trend stability by checking for significant dips.
        Returns a score from 0-1, where 1 is most stable.
        """
        if len(values) < 3:
            return 0.5
        
        # Calculate rolling average to smooth out noise
        window = min(3, len(values) // 4)
        if window < 1:
            window = 1
        
        rolling_avg = np.convolve(values, np.ones(window)/window, mode='valid')
        
        # Check for dips (values that drop significantly below recent average)
        dips = 0
        for i in range(1, len(rolling_avg)):
            if rolling_avg[i] < rolling_avg[i-1] * 0.7:  # 30% drop
                dips += 1
        
        # Stability score: fewer dips = higher score
        stability = 1.0 - (dips / len(rolling_avg))
        return max(0.0, min(1.0, stability))
    
    def analyze_niche(self, niche_name: str, keywords: List[str]) -> Dict:
        """
        Analyze a single niche by fetching data and calculating metrics.
        """
        print(f"Analyzing niche: {niche_name}...")
        
        # Fetch data for all keywords in this niche
        all_data = {}
        timestamps = None
        
        for keyword in keywords:
            data_df = self.fetch_trends_data([keyword])
            if data_df is not None and not data_df.empty and keyword in data_df.columns:
                all_data[keyword] = data_df[keyword].values
                if timestamps is None:
                    timestamps = data_df.index
            time.sleep(1)  # Rate limiting
        
        if not all_data:
            return None
        
        # Aggregate metrics across all keywords in the niche
        growth_scores = []
        volatility_scores = []
        stability_scores = []
        
        for keyword, values in all_data.items():
            growth = self.calculate_growth(values)
            volatility = self.calculate_volatility(values)
            stability = self.calculate_trend_stability(values)
            
            growth_scores.append(growth)
            volatility_scores.append(volatility)
            stability_scores.append(stability)
        
        # Average metrics across keywords
        avg_growth = np.mean(growth_scores) if growth_scores else 0
        avg_volatility = np.mean(volatility_scores) if volatility_scores else 0
        avg_stability = np.mean(stability_scores) if stability_scores else 0
        
        # Calculate volatility vs growth ratio
        # Lower ratio = better (less volatility relative to growth)
        if avg_growth != 0:
            volatility_growth_ratio = abs(avg_volatility / avg_growth)
        else:
            volatility_growth_ratio = float('inf')
        
        return {
            'niche': niche_name,
            'keywords': list(all_data.keys()),
            'growth': avg_growth,
            'volatility': avg_volatility,
            'stability': avg_stability,
            'volatility_growth_ratio': volatility_growth_ratio,
            'data': all_data,
            'timestamps': timestamps
        }
    
    def analyze_all_niches(self) -> Dict:
        """Analyze all niches and return results."""
        niches = self.get_trending_niches()
        results = {}
        
        for niche_name, keywords in niches.items():
            result = self.analyze_niche(niche_name, keywords)
            if result:
                results[niche_name] = result
            time.sleep(2)  # Rate limiting between niches
        
        self.results = results
        return results
    
    def identify_green_light_niches(self, 
                                   min_growth: float = 5.0,
                                   max_volatility_ratio: float = 2.0,
                                   min_stability: float = 0.6) -> List[Dict]:
        """
        Identify "Green Light" niches with steady growth without huge dips.
        
        Criteria:
        - Minimum growth threshold
        - Maximum volatility/growth ratio (lower is better)
        - Minimum stability score
        """
        if not self.results:
            self.analyze_all_niches()
        
        green_light = []
        
        for niche_name, result in self.results.items():
            growth = result['growth']
            ratio = result['volatility_growth_ratio']
            stability = result['stability']
            
            # Check all criteria
            if (growth >= min_growth and 
                ratio <= max_volatility_ratio and 
                ratio != float('inf') and
                stability >= min_stability):
                green_light.append(result)
        
        # Sort by growth (descending)
        green_light.sort(key=lambda x: x['growth'], reverse=True)
        
        return green_light
    
    def plot_trajectories(self, save_path: str = 'niche_trajectories.png'):
        """Plot trajectories for all niches."""
        if not self.results:
            print("No results to plot. Run analyze_all_niches() first.")
            return
        
        # Create figure with subplots
        n_niches = len(self.results)
        cols = 2
        rows = (n_niches + 1) // 2
        
        fig, axes = plt.subplots(rows, cols, figsize=(16, 4 * rows))
        if n_niches == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        for idx, (niche_name, result) in enumerate(self.results.items()):
            ax = axes[idx] if idx < len(axes) else axes[-1]
            
            timestamps = result.get('timestamps')
            
            # Plot each keyword in the niche
            for keyword, values in result['data'].items():
                if timestamps is not None and len(timestamps) == len(values):
                    ax.plot(timestamps, values, 
                           label=keyword, alpha=0.7, linewidth=2)
                else:
                    ax.plot(range(len(values)), values, 
                           label=keyword, alpha=0.7, linewidth=2)
            
            # Add metrics to title
            title = f"{niche_name}\n"
            title += f"Growth: {result['growth']:.1f}% | "
            title += f"Volatility: {result['volatility']:.1f}% | "
            title += f"Ratio: {result['volatility_growth_ratio']:.2f} | "
            title += f"Stability: {result['stability']:.2f}"
            
            ax.set_title(title, fontsize=10, fontweight='bold')
            ax.set_xlabel('Time')
            ax.set_ylabel('Interest Score')
            ax.legend(loc='best', fontsize=8)
            ax.grid(True, alpha=0.3)
            if timestamps is not None:
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Hide unused subplots
        for idx in range(n_niches, len(axes)):
            axes[idx].set_visible(False)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nGraph saved to: {save_path}")
        plt.show()
    
    def plot_combined_trajectory(self, save_path: str = 'combined_trajectories.png'):
        """Plot all niches on a single graph for comparison."""
        if not self.results:
            print("No results to plot. Run analyze_all_niches() first.")
            return
        
        plt.figure(figsize=(16, 8))
        
        # Plot average trend for each niche
        for niche_name, result in self.results.items():
            # Calculate average across all keywords in niche
            all_values = []
            for values in result['data'].values():
                if len(values) > 0:
                    all_values.append(values)
            
            if all_values:
                # Align arrays by length
                min_len = min(len(v) for v in all_values)
                aligned = [v[:min_len] for v in all_values]
                avg_values = np.mean(aligned, axis=0)
                
                timestamps = result.get('timestamps')
                if timestamps is not None and len(timestamps) >= min_len:
                    plt.plot(timestamps[:min_len], avg_values, 
                            label=niche_name, linewidth=2.5, marker='o', markersize=4)
                else:
                    plt.plot(range(len(avg_values)), avg_values, 
                            label=niche_name, linewidth=2.5, marker='o', markersize=4)
        
        plt.title('Trending Dropshipping Niches - Interest Over Time (Last 12 Months)', 
                 fontsize=16, fontweight='bold', pad=20)
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Google Trends Interest Score', fontsize=12)
        plt.legend(loc='best', fontsize=10, framealpha=0.9)
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nCombined graph saved to: {save_path}")
        plt.show()


def main():
    """Main function to run the analysis."""
    print("=" * 70)
    print("TRENDING DROPSHIPPING NICHES ANALYZER")
    print("=" * 70)
    print("\nAnalyzing niches using Google Trends data...")
    print("This may take a few minutes due to rate limiting.\n")
    
    # Initialize analyzer
    analyzer = NichesAnalyzer()
    
    # Analyze all niches
    results = analyzer.analyze_all_niches()
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)
    
    # Identify Green Light niches
    green_light = analyzer.identify_green_light_niches(
        min_growth=5.0,
        max_volatility_ratio=2.0,
        min_stability=0.6
    )
    
    # Print results
    print("\n" + "=" * 70)
    print("GREEN LIGHT NICHES - Steady Growth Without Huge Dips")
    print("=" * 70)
    
    if green_light:
        for idx, niche in enumerate(green_light, 1):
            print(f"\n{idx}. {niche['niche']}")
            print(f"   Growth: {niche['growth']:.2f}%")
            print(f"   Volatility: {niche['volatility']:.2f}%")
            print(f"   Volatility/Growth Ratio: {niche['volatility_growth_ratio']:.2f}")
            print(f"   Stability Score: {niche['stability']:.2f}")
            print(f"   Keywords analyzed: {', '.join(niche['keywords'][:3])}...")
    else:
        print("\nNo niches met the 'Green Light' criteria.")
        print("Try adjusting the thresholds in identify_green_light_niches().")
    
    # Print all niches summary
    print("\n" + "=" * 70)
    print("ALL NICHES SUMMARY")
    print("=" * 70)
    for niche_name, result in results.items():
        print(f"\n{niche_name}:")
        print(f"  Growth: {result['growth']:.2f}%")
        print(f"  Volatility: {result['volatility']:.2f}%")
        print(f"  Ratio: {result['volatility_growth_ratio']:.2f}")
        print(f"  Stability: {result['stability']:.2f}")
    
    # Create visualizations
    print("\n" + "=" * 70)
    print("GENERATING VISUALIZATIONS")
    print("=" * 70)
    
    analyzer.plot_combined_trajectory()
    analyzer.plot_trajectories()
    
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()


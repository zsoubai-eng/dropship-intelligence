import time
import pandas as pd
from pytrends.request import TrendReq
import matplotlib.pyplot as plt
import random

# Core Directives: Safety & Data-Driven
# 1. Niches identified from Market Research
NICHES = ["Eco Friendly", "Smart Pet", "Sleep Technology"]

def fetch_trends():
    # Initialize Pytrends
    # Removed retries/backoff_factor due to urllib3 'method_whitelist' compatibility issue
    pytrends = TrendReq(hl='en-US', tz=360)
    
    all_data = pd.DataFrame()

    print("Starting Trend Hunting...")
    
    for niche in NICHES:
        print(f"[*] Fetching data for: {niche}")
        try:
            # Build payload for single keyword to see individual shape
            # Timeframe: Past 12 months to see recent steady growth
            pytrends.build_payload([niche], cat=0, timeframe='today 12-m')
            
            # Get interest over time
            data = pytrends.interest_over_time()
            
            if not data.empty:
                # Remove partial data indicator
                if 'isPartial' in data.columns:
                    data = data.drop(columns=['isPartial'])
                
                # Merge into main dataframe
                if all_data.empty:
                    all_data = data
                else:
                    all_data = all_data.join(data)
            else:
                print(f"[!] No data found for {niche}")

        except Exception as e:
            print(f"[!] Error fetching {niche}: {e}")
        
        # SAFETY: The "Human Pace" Rule
        # Sleep 10 seconds between requests to avoid 429
        sleep_time = 10 + random.uniform(1, 3) # Add a little jitter
        print(f"Sleeping for {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)

    return all_data

def plot_trends(data):
    if data.empty:
        print("No data to plot.")
        return

    plt.figure(figsize=(10, 6))
    
    for column in data.columns:
        plt.plot(data.index, data[column], label=column, linewidth=2)
    
    plt.title('Niche Interest Over Time (Last 12 Months)')
    plt.xlabel('Date')
    plt.ylabel('Interest (Normalized 0-100)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Analyze steady growth logic (simple variance/slope check visual)
    plt.tight_layout()
    
    output_file = 'trends_graph.png'
    plt.savefig(output_file)
    print(f"Graph saved to {output_file}")

if __name__ == "__main__":
    trends_data = fetch_trends()
    
    # Save raw data as per "One File Truth" rule
    trends_data.to_csv("trends_data.csv")
    print("Data saved to trends_data.csv")
    
    plot_trends(trends_data)

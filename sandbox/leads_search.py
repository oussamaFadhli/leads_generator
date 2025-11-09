"""
Example of Search Graph
"""

import os
import json

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Dict

from scrapegraphai.graphs import SearchGraph

from schema.leads_schema import LeadsSearchResult

load_dotenv()

# ************************************************
# Define the configuration for the graph
# ************************************************
saas_info = {
  "name": "Trucking88",
  "one_liner": "A next-generation trucking TMS designed to increase efficiency and profitability for trucking companies.",
  "features": [
    {
      "name": "Order Management",
      "desc": "Improve efficiency with tools to prevent lost orders and miscommunication between drivers and dispatchers, leading to timely deliveries and satisfied customers."
    },
    {
      "name": "Live Order Updates",
      "desc": "Track and monitor the status of each load with GPS tracking and in-app messaging, providing real-time updates to reduce errors and foster stronger client relationships."
    },
    {
      "name": "AI Driven Rate Confirmation Importer",
      "desc": "Automatically import any rate confirmation in just a few clicks, eliminating the need to manually type every rate confirmation when creating a new order."
    },
    {
      "name": "Fuel Calculator",
      "desc": "Identify fuel stops along your route and receive suggestions for the best fuel stations to maximize savings, potentially saving your company $10-$30 per fueling."
    },
    {
      "name": "Financial Dashboard",
      "desc": "Access financial data from your phone or app 24/7, providing up-to-the-minute data on your company's revenue, expenses, and profitability, and monitoring driver performance in terms of revenue generated."
    },
    {
      "name": "Mobile App for Drivers",
      "desc": "A web-based mobile app for drivers to manage their loads, check in, adjust load status, scan PODs, and more."
    }
  ],
  "pricing": [
    {
      "plan_name": "Free",
      "price": "Free",
      "features": [
        "Basic order management",
        "Limited live order updates",
        "Access to mobile app for drivers"
      ],
      "link": "https://trucking88.com/signup"
    }
  ],
  "target_segments": [
    "Trucking Companies",
    "Fleet Managers",
    "Logistics Providers",
    "Small to Medium-sized Trucking Businesses"
  ]
}

prompt_dict = f"""
Based on the following SaaS project information, search the internet for:
1. Famous competitors: Identify key competitors in the market.
2. Strengths and Weaknesses: For each competitor, list their main strengths and weaknesses.
3. Related Subreddits: Find the best subreddits related to the project's interests.

SaaS Project Information:
{json.dumps(saas_info, indent=2)}

Please provide the output in a JSON format that matches the Pydantic schema:
{LeadsSearchResult.schema_json(indent=2)}
"""
 
nvidia_key = os.getenv("NVIDIA_KEY")

graph_config = {
    "llm": {
        "api_key": nvidia_key,
        "model": "nvidia/mistralai/mistral-nemotron",
        "temperature": 0,
        "format": "json",  # Ollama needs the format to be specified explicitly
    },
    "max_results": 7,
    "verbose": True,
    "headless": False,
}

# ************************************************
# Create the SearchGraph instance and run it
# ************************************************

search_graph = SearchGraph(
    prompt=prompt_dict, config=graph_config
)

result = search_graph.run()
print(result)

# Save the result to a JSON file
with open("leads_search_result.json", "w") as f:
    json.dump(result, f, indent=4)

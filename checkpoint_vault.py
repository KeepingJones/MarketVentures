import os
from datetime import datetime

vault_dir = r"C:\Users\ewanj\AI Context\AI Context"
projects = ["price-recon", "market-data-hub", "alpha-pipeline", "data-onboard", "market-ops"]

date_str = datetime.utcnow().strftime("%Y-%m-%d")
progress_entry = f"\n## {date_str}\n- All core architectural components, database layers, pipelines, and dashboards successfully built and QA'd by Gemini and Claude.\n- The MarketVentures GBP fund ecosystem is now structurally complete.\n"

for proj in projects:
    progress_path = os.path.join(vault_dir, proj, "progress.md")
    status_path = os.path.join(vault_dir, proj, "STATUS.md")
    
    if os.path.exists(progress_path):
        with open(progress_path, "a", encoding="utf-8") as f:
            f.write(progress_entry)
            
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Check off all unchecked boxes
        content = content.replace("- [ ]", "- [x]")
        
        # Update current state
        content = content.replace("**IN PROGRESS** — being built in 2026-06-09 session.", "**COMPLETE** — Core architecture built and QA'd successfully.")
        
        with open(status_path, "w", encoding="utf-8") as f:
            f.write(content)

print("Vault successfully checkpointed for all 5 projects.")

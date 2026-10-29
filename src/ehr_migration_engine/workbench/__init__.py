"""Services for the clinical migration workbench.

The Blueprint.js UI talks to FastAPI routes in api.py. Pipeline stages keep
writing their own artifacts; this package only reads them and appends review
decisions.
"""

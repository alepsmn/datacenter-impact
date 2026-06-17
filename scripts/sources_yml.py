content = """version: 2

sources:
  - name: datacenter_impact
    database: totemic-life-499613-f2
    schema: datacenter_impact
    tables:
      - name: eia_electricity"""

open("models/staging/sources.yml", "w").write(content)
print("OK")
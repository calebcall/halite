# Previewing the Halite docs locally

```bash
cd docs
npx mint dev        # serves at http://localhost:3000
npx mint broken-links   # validate internal links
```

The API reference renders from `api/openapi.json`. Regenerate that file after
backend schema changes with `../scripts/gen-openapi.sh` (see the "Regenerating
the API spec" page).

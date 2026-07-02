# DMath 3D Printing Inventory — Shiny App

Browse inventory photos, on-hand counts, and per-item download files.

## Prerequisites

Install R packages (once):

```r
install.packages(c("shiny", "bslib", "yaml"))
```

## Run locally

From the repo root:

```r
shiny::runApp("Inventory/shiny-app")
```

Or from terminal:

```bash
R -e "shiny::runApp('Inventory/shiny-app')"
```

The app loads data from the parent `Inventory/` folder (`inventory.yml`, `Photos/`, `items/`).

## Folder layout

```
Inventory/
├── inventory.yml          # titles, counts, descriptions, Forms URL
├── Photos/                # one .png per item (filename = item id)
├── items/
│   └── <item-id>/
│       └── STLs and GCODEs/   # drop up to 10 downloadable files here
└── shiny-app/
    ├── app.R
    └── www/
        └── styles.css
```

**Item IDs** (must match photo filenames):

| ID | Title |
|----|-------|
| `student-medium-3d-integral-shape` | Student Medium 3D Integral Shape |
| `thermoformed-mountains` | Thermoformed Mountains |
| `surface-of-revolution-sphere-kit` | Surface of Revolution Sphere Kit |
| `wyndor-feasability-region` | Wyndor Feasability Region |
| `black-and-gold-mountains` | Black and Gold Mountains |
| `student-triple-integral-activity-kit` | Student Triple Integral Activity Kit |
| `instructor-large-yellow-3d-shape` | Instructor Large Yellow 3D Shape |
| `1st-octant-ma204-wpr-ay26-2` | 1st Octant MA204 WPR AY26-2 |

## Update inventory counts

Edit [`../inventory.yml`](../inventory.yml). Example for a single count:

```yaml
  - id: thermoformed-mountains
    title: "Thermoformed Mountains"
    count: 31
    description: ""
```

Item 1 uses variant breakdown:

```yaml
  - id: student-medium-3d-integral-shape
    count: 15
    variants:
      - label: "Black"
        count: 10
      - label: "Grey"
        count: 5
```

Restart or refresh the app after editing.

## Add download files

1. Drop files into `Inventory/items/<item-id>/STLs and GCODEs/` (recommended max 10 per item).
2. Refresh the app — files appear automatically on that item's detail page.
3. Hidden files (names starting with `.`) are ignored.

## Microsoft Forms link

Paste your form URL into `inventory.yml`:

```yaml
request_form_url: "https://forms.office.com/..."
```

The homepage footer link appears once the URL is set.

## Deploy to shinyapps.io

Deploy the **Inventory** folder so photos, manifest, and item files are bundled:

```r
install.packages("rsconnect")
rsconnect::deployApp(
  appDir = "Inventory",
  appPrimaryDoc = "shiny-app/app.R",
  appFiles = c(
    "shiny-app/app.R",
    "shiny-app/www",
    "inventory.yml",
    "Photos",
    "items"
  )
)
```

Redeploy whenever you add download files or change counts in `inventory.yml`.

## Notes

- More than 10 files per item still works, but a warning is logged server-side.
- Descriptions are optional; leave `description: ""` until you have text to show.

library(shiny)
library(bslib)
library(yaml)

resolve_app_root <- function() {
  for (candidate in c(".", "..")) {
    manifest <- file.path(candidate, "inventory.yml")
    if (file.exists(manifest)) {
      return(normalizePath(candidate, winslash = "/"))
    }
  }
  stop("Could not find inventory.yml in the app directory or its parent.")
}

app_root <- resolve_app_root()

inventory <- yaml::read_yaml(file.path(app_root, "inventory.yml"))
items <- inventory$items

addResourcePath("photos", file.path(app_root, "Photos"))
addResourcePath("item-files", file.path(app_root, "items"))

list_item_files <- function(item_id) {
  files_dir <- file.path(app_root, "items", item_id, "files")
  if (!dir.exists(files_dir)) {
    return(character())
  }
  files <- list.files(files_dir, full.names = TRUE, no.. = TRUE)
  files[!grepl("^\\.", basename(files))]
}

format_count <- function(item) {
  if (!is.null(item$variants) && length(item$variants) > 0) {
    breakdown <- paste(
      vapply(
        item$variants,
        function(v) sprintf("%d %s", v$count, tolower(v$label)),
        character(1)
      ),
      collapse = ", "
    )
    sprintf("%s (%d total)", breakdown, item$count)
  } else {
    as.character(item$count)
  }
}

get_item <- function(item_id) {
  idx <- which(vapply(items, function(x) x$id == item_id, logical(1)))
  if (length(idx) == 0) NULL else items[[idx[1]]]
}

null_or <- function(x, fallback = "") {
  if (is.null(x) || length(x) == 0) fallback else x
}

home_grid_ui <- function() {
  cards <- lapply(items, function(item) {
    div(
      class = "inventory-card",
      actionButton(
        inputId = paste0("select_", item$id),
        label = NULL,
        class = "inventory-card-button",
        div(
          class = "inventory-card-inner",
          tags$img(
            src = paste0("photos/", item$id, ".png"),
            alt = item$title,
            class = "inventory-card-image"
          ),
          div(
            class = "inventory-card-title",
            sprintf("%s (%d)", item$title, item$count)
          )
        )
      )
    )
  })

  tagList(
    div(class = "page-header", h1(inventory$app_title)),
    div(class = "inventory-grid", cards),
    footer_ui()
  )
}

footer_ui <- function() {
  form_url <- null_or(inventory$request_form_url, "")
  if (!nzchar(trimws(form_url))) {
    return(
      div(
        class = "page-footer page-footer-muted",
        "Request form link coming soon."
      )
    )
  }

  div(
    class = "page-footer",
    tags$a(
      href = form_url,
      target = "_blank",
      rel = "noopener noreferrer",
      "Can't find what you're looking for? Request a new print"
    )
  )
}

detail_ui <- function(item) {
  files <- list_item_files(item$id)
  description_block <- if (nzchar(trimws(null_or(item$description, "")))) {
    div(class = "detail-description", item$description)
  }

  downloads_block <- if (length(files) == 0) {
    div(class = "downloads-empty", "No files uploaded yet.")
  } else {
    if (length(files) > 10) {
      warning(
        "Item ", item$id, " has ", length(files),
        " files (recommended max is 10)."
      )
    }
    tagList(
      h3("Downloads"),
      div(
        class = "download-list",
        lapply(seq_along(files), function(i) {
          file_name <- basename(files[i])
          tags$a(
            class = "btn btn-outline-primary download-link",
            href = paste0(
              "item-files/", item$id, "/files/",
              utils::URLencode(file_name, reserved = TRUE)
            ),
            download = file_name,
            file_name
          )
        })
      )
    )
  }

  tagList(
    div(
      class = "detail-header",
      actionButton("back_home", "Back", class = "btn-secondary back-button")
    ),
    div(
      class = "detail-content",
      div(
        class = "detail-image-col",
        tags$img(
          src = paste0("photos/", item$id, ".png"),
          alt = item$title,
          class = "detail-image"
        )
      ),
      div(
        class = "detail-info-col",
        h2(item$title),
        div(
          class = "detail-count",
          tags$strong("On hand: "),
          format_count(item)
        ),
        description_block,
        div(class = "detail-downloads", downloads_block)
      )
    )
  )
}

ui <- page_fluid(
  theme = bs_theme(version = 5, bootswatch = "flatly"),
  tags$head(tags$link(rel = "stylesheet", type = "text/css", href = "styles.css")),
  uiOutput("main_ui")
)

server <- function(input, output, session) {
  selected_item <- reactiveVal(NULL)

  output$main_ui <- renderUI({
    item_id <- selected_item()
    if (is.null(item_id)) {
      home_grid_ui()
    } else {
      detail_ui(get_item(item_id))
    }
  })

  observeEvent(input$back_home, {
    selected_item(NULL)
  })

  lapply(items, function(item) {
    observeEvent(input[[paste0("select_", item$id)]], {
      selected_item(item$id)
    }, ignoreInit = TRUE)
  })
}

shinyApp(ui, server)

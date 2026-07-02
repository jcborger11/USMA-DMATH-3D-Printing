library(shiny)
library(bslib)
library(yaml)

STLS_GCODE_FOLDER <- "STLs and GCODEs"

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

list_visible_files <- function(dir_path) {
  if (!dir.exists(dir_path)) {
    return(character())
  }
  entries <- list.files(dir_path, full.names = TRUE, no.. = TRUE)
  entries[!file.info(entries)$isdir & !grepl("^\\.", basename(entries))]
}

list_item_root_files <- function(item_id) {
  list_visible_files(file.path(app_root, "items", item_id))
}

list_stls_gcode_files <- function(item_id) {
  list_visible_files(file.path(app_root, "items", item_id, STLS_GCODE_FOLDER))
}

stls_gcode_folder_exists <- function(item_id) {
  dir.exists(file.path(app_root, "items", item_id, STLS_GCODE_FOLDER))
}

encode_item_path <- function(relative_path) {
  segments <- strsplit(relative_path, "/", fixed = TRUE)[[1]]
  paste(
    vapply(segments, utils::URLencode, character(1), reserved = TRUE),
    collapse = "/"
  )
}

file_download_link <- function(item_id, relative_path, label = NULL) {
  file_name <- basename(relative_path)
  tags$a(
    class = "btn btn-outline-primary download-link",
    href = paste0("item-files/", item_id, "/", encode_item_path(relative_path)),
    download = file_name,
    label %||% file_name
  )
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

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x

app_css <- function() {
  css_paths <- c(
    file.path("www", "styles.css"),
    file.path("shiny-app", "www", "styles.css"),
    file.path(app_root, "shiny-app", "www", "styles.css")
  )
  css_path <- css_paths[file.exists(css_paths)][1]
  if (is.na(css_path)) {
    warning("Could not find styles.css")
    return(NULL)
  }
  includeCSS(css_path)
}

home_grid_ui <- function() {
  cards <- lapply(items, function(item) {
    div(
      class = "inventory-card",
      actionButton(
        inputId = paste0("select_", item$id),
        label = div(
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
        ),
        class = "inventory-card-button"
      )
    )
  })

  tagList(
    div(
      class = "inventory-page",
      div(class = "page-header", h1(inventory$app_title)),
      div(class = "inventory-grid", cards),
      footer_ui()
    )
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

folder_button <- function(folder_name) {
  actionButton(
    inputId = "open_stls_gcode_folder",
    label = NULL,
    class = "folder-button",
    div(
      class = "folder-button-inner",
      tags$span(class = "folder-icon", "📁"),
      tags$span(class = "folder-name", folder_name)
    )
  )
}

file_list_ui <- function(item_id, files, path_prefix = "") {
  if (length(files) == 0) {
    return(NULL)
  }

  div(
    class = "download-list",
    lapply(files, function(file_path) {
      relative_path <- if (nzchar(path_prefix)) {
        file.path(path_prefix, basename(file_path))
      } else {
        basename(file_path)
      }
      file_download_link(item_id, relative_path)
    })
  )
}

item_root_files_ui <- function(item) {
  root_files <- list_item_root_files(item$id)
  has_subfolder <- stls_gcode_folder_exists(item$id)

  root_links <- file_list_ui(item$id, root_files)
  folder_block <- if (has_subfolder) folder_button(STLS_GCODE_FOLDER) else NULL

  if (is.null(root_links) && is.null(folder_block)) {
    return(div(class = "downloads-empty", "No files uploaded yet."))
  }

  tagList(
    h3("Files"),
    root_links,
    folder_block
  )
}

subfolder_files_ui <- function(item) {
  files <- list_stls_gcode_files(item$id)

  if (length(files) == 0) {
    return(div(class = "downloads-empty", "No files in this folder yet."))
  }

  if (length(files) > 10) {
    warning(
      "Item ", item$id, " has ", length(files),
      " files in ", STLS_GCODE_FOLDER, " (recommended max is 10)."
    )
  }

  tagList(
    h3(STLS_GCODE_FOLDER),
    file_list_ui(item$id, files, path_prefix = STLS_GCODE_FOLDER)
  )
}

detail_ui <- function(item, subfolder = NULL) {
  description_block <- if (nzchar(trimws(null_or(item$description, "")))) {
    div(class = "detail-description", item$description)
  }

  in_subfolder <- identical(subfolder, STLS_GCODE_FOLDER)

  header_buttons <- if (in_subfolder) {
    tagList(
      actionButton("back_item_root", "Back to item", class = "btn-secondary back-button"),
      div(class = "breadcrumb", paste(item$title, "›", STLS_GCODE_FOLDER))
    )
  } else {
    actionButton("back_home", "Back", class = "btn-secondary back-button")
  }

  files_block <- if (in_subfolder) {
    subfolder_files_ui(item)
  } else {
    item_root_files_ui(item)
  }

  tagList(
    div(class = "detail-header", header_buttons),
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
        div(class = "detail-downloads", files_block)
      )
    )
  )
}

ui <- page_fluid(
  theme = bs_theme(version = 5, bootswatch = "flatly"),
  tags$head(app_css()),
  uiOutput("main_ui")
)

server <- function(input, output, session) {
  selected_item <- reactiveVal(NULL)
  selected_subfolder <- reactiveVal(NULL)

  output$main_ui <- renderUI({
    item_id <- selected_item()
    if (is.null(item_id)) {
      home_grid_ui()
    } else {
      detail_ui(get_item(item_id), subfolder = selected_subfolder())
    }
  })

  observeEvent(input$back_home, {
    selected_item(NULL)
    selected_subfolder(NULL)
  })

  observeEvent(input$back_item_root, {
    selected_subfolder(NULL)
  })

  observeEvent(input$open_stls_gcode_folder, {
    selected_subfolder(STLS_GCODE_FOLDER)
  })

  lapply(items, function(item) {
    observeEvent(input[[paste0("select_", item$id)]], {
      selected_item(item$id)
      selected_subfolder(NULL)
    }, ignoreInit = TRUE)
  })
}

shinyApp(ui, server)

library(networkD3)
library(htmlwidgets)

# Nodes
Players <- data.frame(
  name = c(
    "Donald Trump Jr.", 
    "Robert F. Kennedy Jr.",
    "Laura Loomer",
    "Matt Gaetz",
    "Dr. Robert Malone",
    "Dr. Marty Makary",
    "Children's Health Defense",
    "Dr. William Parker",
    "Dr. Jay Bhattacharya",
    "Dr. Mehmet Oz",
    "Nick Sortor",
    "Alex Clark",
    "Moms Across America",
    "Joe Rogan",
    "The Wall Street Journal",
    "Bloomberg TV",
    "Fox News",
    "The Daily Caller",
    "Infowars",
    "Dr. Andrea Baccarelli",
    "Harvard School of Public Health",
    "The Atlantic"
  ),
  group = c(
    "Executive Branch", 
    "Executive Branch", 
    "Influencer", 
    "Influencer", 
    "Executive Branch", 
    "Executive Branch",
    "Non-Government Organization",
    "Researcher",
    "Executive Branch",
    "Executive Branch",
    "Influencer",
    "Influencer",
    "Non-Government Organization",
    "Influencer",
    "Press",
    "Press",
    "Press",
    "Press",
    "Press",
    "Researcher",
    "Non-Government Organization",
    "Press"
  )
)

# Edges (0-based indexing)
Edges <- data.frame(
  source = c(
      0, 1, 5, 1, 1, # Executive
      1, 1, 2, 8, 19, 18, # Non-govt professional associations  
      2, 2, 2, 2, 3, 10, 13, 6, # Influencers and orgs "reporting"
      14, 18, 18, 15, 5, 5, 5, 16, 17, 1, 21, 21, 21 # Actual reporting (mostly)
    ),
  target = c(
      1, 5, 4, 8, 9, # Executive
      6, 7, 7, 7, 20, 13, # Non-govt professional associations
      0, 1, 16, 7, 4, 1, 20, 14, #Influencers and orgs"reporting"
      1, 14, 1, 5, 14, 19, 16, 9, 1, 17, 1, 7, 8 # Actual reporting (mostly)
    ),
  value = c(
      1, 1, 1, 1, 1, # Executive
      1, 1, 1, 1, 1, 1, # Non-govt professional associations 
      1, 1, 1, 1, 1, 1, 1, 1, # Influencers and orgs "reporting"
      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 # Actual reporting (mostly)
    )
)

# Plot
p <- forceNetwork(
  Links = Edges,
  Nodes = Players,
  Source = "source",
  Target = "target",
  Value = "value",
  NodeID = "name",
  Group = "group",
  fontSize = 12,
  fontFamily = "sans-serif",
  opacity = 0.9,
  colourScale = JS("d3.scaleOrdinal(d3.schemeCategory10);"),
  zoom = TRUE,
  arrows = TRUE,
  legend = TRUE
)

p


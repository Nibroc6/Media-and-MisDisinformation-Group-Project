library(networkD3)

# Nodes
Players <- data.frame(
  name = c(
    "0 Donald Trump Jr.", 
    "1 Robert F. Kennedy Jr.",
    "2 Laura Loomer",
    "3 Matt Gaetz",
    "4 Dr. Robert Malone",
    "5 Dr. Marty Makary",
    "6 Children's Health Defense",
    "7 Dr. William Parker",
    "8 Dr. Jay Bhattacharya",
    "9 Dr. Mehmet Oz",
    "10 Nick Sortor",
    "11 Alex Clark",
    "12 Moms Across America",
    "13 Joe Rogan",
    "14 The Wall Street Journal",
    "15 Bloomberg TV",
    "16 Fox News",
    "17 The Daily Caller",
    "18 Infowars",
    "19 Dr. Andrea Baccarelli",
    "20 Harvard School of Public Health",
    "21 The Atlantic"
  ),
  # Group Key:
  # 1 = Executive Branch
  # 2 = Influencer
  # 3 = Organization
  # 4 = Researcher
  # 5 = Press
  group = c(
    1, 
    1, 
    2, 
    2, 
    1, 
    1,
    3,
    4,
    1,
    1,
    2,
    2,
    3,
    2,
    5,
    5,
    5,
    5,
    5,
    4,
    3,
    5
  )
)

# Edges (0-based indexing)
Edges <- data.frame(
  source = c(
      0, 1, 5, 1, 1, # Executive
      1, 1, 2, 8, # Non-govt professional associations  
      2, 2, 2, 2, 3,  # Influencers and orgs "reporting"
      14 # Actual reporting (mostly)
    ),
  target = c(
      1, 5, 4, 8, 9, # Executive
      6, 7, 7, 7, # Non-govt professional associations
      0, 1, 16, 7, 4, #Influencers and orgs"reporting"
      1 # Actual reporting (mostly)
    ),
  value = c(
      1, 1, 1, 1, 1, # Executive
      1, 1, 1, 1, # Non-govt professional associations 
      1, 1, 1, 1, 1, # Influencers and orgs "reporting"
      1 # Actual reporting (mostly)
    )
)

# Plot
forceNetwork(
  Links = Edges,
  Nodes = Players,
  Source = "source",
  Target = "target",
  Value = "value",
  NodeID = "name",
  Group = "group",
  opacity = 0.7,
  colourScale = JS("d3.scaleOrdinal(d3.schemeCategory20);"),
  zoom = TRUE
)

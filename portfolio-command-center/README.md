# IT/CS Portfolio Command Center

A searchable static showcase of all 60 cataloged repository projects: 25 core applications, the 30-project IT/CS program, and five additional learning repositories. Cards show each project's collection, area, short purpose, technology stack when available, and a direct link to its README. Project metadata lives in `projects.json`; the frontend uses browser-native JavaScript and works without a build step.

## Run

Serve the repository root with `python -m http.server 8000`, then visit `/portfolio-command-center/`. Search matches project names, summaries, categories, collections, and technology stacks. Use the category buttons to narrow the collection. Each card links to the corresponding project README. This showcase describes repository projects; it does not claim that they are deployed or production-ready.

The data is curated in `projects.json`. Keep IDs unique, preserve repository-relative README paths, and update the browser showcase check when the catalog changes.

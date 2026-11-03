const projectList = document.querySelector('#projects');
const search = document.querySelector('#search');
const filters = document.querySelector('#filters');
const count = document.querySelector('#count');

let projects = [];
let activeCategory = 'All';

function renderProjects() {
  const query = search.value.trim().toLocaleLowerCase();
  const visibleProjects = projects.filter((project) => {
    const searchableText = [
      project.name,
      project.category,
      project.summary,
      project.stack,
      project.program,
    ].filter(Boolean).join(' ').toLocaleLowerCase();

    return (activeCategory === 'All' || project.category === activeCategory)
      && searchableText.includes(query);
  });

  count.textContent = `Showing ${visibleProjects.length} of ${projects.length} projects`;
  projectList.replaceChildren(...visibleProjects.map(createProjectCard));
}

function createProjectCard(project) {
  const article = document.createElement('article');
  article.className = 'card';

  const tag = document.createElement('p');
  tag.className = 'tag';
  const programLabel = project.programNumber
    ? `30-project #${String(project.programNumber).padStart(2, '0')}`
    : `${project.program ?? 'Core portfolio'} #${String(project.id).padStart(2, '0')}`;
  tag.textContent = `${programLabel} · ${project.category}`;

  const title = document.createElement('h2');
  title.textContent = project.name;

  const description = document.createElement('p');
  description.textContent = project.summary;

  article.append(tag, title, description);

  if (project.stack) {
    const stack = document.createElement('p');
    stack.className = 'stack';
    stack.textContent = project.stack;
    article.append(stack);
  }

  const link = document.createElement('a');
  link.href = project.path;
  link.textContent = 'Project details';
  link.setAttribute('aria-label', `${project.name} project details`);
  article.append(link);

  return article;
}

function createCategoryFilters() {
  const categories = ['All', ...new Set(projects.map((project) => project.category))];
  const buttons = categories.map((category) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = category;
    button.setAttribute('aria-pressed', String(category === activeCategory));
    button.addEventListener('click', () => {
      activeCategory = category;
      for (const filter of filters.children) {
        filter.setAttribute('aria-pressed', String(filter.textContent === category));
      }
      renderProjects();
    });
    return button;
  });

  filters.replaceChildren(...buttons);
}

fetch('projects.json')
  .then((response) => {
    if (!response.ok) throw new Error('Could not load project catalogue');
    return response.json();
  })
  .then((catalogue) => {
    if (!Array.isArray(catalogue)) throw new Error('Project catalogue must be a list');
    projects = catalogue;
    createCategoryFilters();
    renderProjects();
  })
  .catch((error) => {
    count.textContent = error.message;
  });

search.addEventListener('input', renderProjects);

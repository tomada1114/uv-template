"""Self-checks of the agent harness: cross-file drift fails CI, not an agent.

`just check-harness` runs this package (and `tests/test_product_section.py`);
`just verify` and CI's test shards run it too. Each check passes on the
repository and fails on a fixture built under ``tmp_path``:

- (a) ``test_skills.py``: every ``.agents/skills/<dir>/SKILL.md`` frontmatter
  holds only ``name`` (equal to ``<dir>``) and an ASCII ``description`` within
  the authoring-skills limit, the body is at most 200 lines, and no nested
  ``SKILL.md`` exists;
- (b) ``test_skills.py``: AGENTS.md's Skills table lists exactly those skills;
- (c) ``test_just_recipes.py``: every ``just <recipe>`` named in AGENTS.md,
  CLAUDE.md, the skills, ``.github/**``, README.md, CONTRIBUTING.md,
  ``docs/**`` (bar a superseded or rejected ADR), and the agent definitions
  exists in the justfile;
- (d) ``test_ruleset_contexts.py``: every required context in
  ``.github/rulesets/main.json`` is a job that runs on every pull request and
  cannot be skipped, and one with ``needs:`` has a step, in one of the
  shapes ``_needs.py`` lists, that fails when a needed job's result is not
  ``success``;
- (e) ``test_labels.py``: every label pr-label.yml, the issue forms, and
  dependabot.yml apply is declared exactly once in ``.github/labels.yml``;
- (f) ``test_workflow_hygiene.py``: workflow hygiene (SHA pins, timeouts,
  top-level permissions, checkout credentials, no fail-open constructs, push
  runs on main never cancelled by concurrency), and the same pin, checkout,
  and ``continue-on-error`` rules for the steps of a composite action under
  ``.github/actions/``;
- (g) the Product section check is ``tests/test_product_section.py`` (#95),
  not duplicated here.

The checks hold in the template and in an app the bootstrap cut from it, so
none assumes a template-only file exists. No YAML library is a dependency:
``_yaml.py`` is a fail-closed block scanner, and ``_workflows.py`` reads the
workflow layout on top of it.
"""

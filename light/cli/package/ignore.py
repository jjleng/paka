common_blacklist = [
    ".DS_Store",
    ".idea/*",
    ".vscode/*",
    "*.log",
    "*.pem",
    "*.cert",
    "*.key",
    "*.pfx",
    "*.crt",
    "*.csr",
    "*.srl",
    "*.git",
    "*.der",
    ".coverage",
    ".coverage.*",
]

python_blacklist = common_blacklist + [
    "__pycache__/*",
    "*.py[cod]",
    "*$py.class",
    "*.so",
    ".Python",
    "build/*",
    "develop-eggs/*",
    "dist/*",
    "downloads/*",
    "eggs/*",
    ".eggs/*",
    "lib/*",
    "lib64/*",
    "parts/*",
    "sdist/*",
    "var/*",
    "wheels/*",
    "share/python-wheels/*",
    "*.egg-info/*",
    ".installed.cfg",
    "*.egg",
    "MANIFEST",
    "*.manifest",
    "*.spec",
    "pip-log.txt",
    "pip-delete-this-directory.txt",
    "htmlcov/*",
    ".tox/*",
    ".nox/*",
    ".cache",
    "nosetests.xml",
    "coverage.xml",
    "*.cover",
    "*.py,cover",
    ".hypothesis/*",
    ".pytest_cache/*",
    "cover/*",
    "*.mo",
    "*.pot",
    "local_settings.py",
    "db.sqlite3",
    "db.sqlite3-journal",
    "instance/*",
    ".webassets-cache",
    ".scrapy",
    "docs/_build/*",
    "docs/_output/*",
    "target/*",
    ".ipynb_checkpoints",
    ".python-version",
    "celerybeat-schedule",
    "*.sage.py",
    ".venv/*",
    "venv/*",
    "ENV/*",
    "env/*",
    "bin/*",
    "pyvenv.cfg",
    "Pipfile.lock",
    ".spyderproject",
    ".spyproject",
    ".ropeproject",
    "/site",
    ".mypy_cache/*",
    ".dmypy.json",
    "dmypy.json",
    ".pyre/*",
    ".pytype/*",
    "cython_debug/*",
    "poetry.lock",
    ".pypoetry-cache",
]

nodejs_blacklist = common_blacklist + [
    "node_modules/*",
    "npm-debug.log*",
    "yarn-debug.log*",
    "yarn-error.log*",
    ".yarn-integrity",
    ".env",
    ".env.test",
    ".cache",
    ".next",
    ".out",
    ".nuxt",
    "netlify.toml",
    ".netlify/*",
    "public/sw.js",
    "public/workbox-*.*.js",
    "public/styles.*.js",
    "dist/*",
    ".cache/*",
    ".nyc_output/*",
    "logs/*",
    "package-lock.json",
    "yarn.lock",
    "pnp.*",
    "docker-compose.yml",
    ".dockerignore",
    ".gitattributes",
    ".editorconfig",
    ".eslintignore",
    ".eslintrc.js",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".prettierrc",
    ".prettierrc.js",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierignore",
    "babel.config.js",
    ".babelrc",
    ".babelrc.js",
    ".babelrc.json",
    "jest.config.js",
    "jest.setup.js",
    "tsconfig.json",
    "tslint.json",
    "webpack.config.js",
    "rollup.config.js",
    "gulpfile.js",
    "Gruntfile.js",
    "pnpm-lock.yaml",
    ".pnpm/*",
    ".pnpm-debug.log*",
]

blacklist = list(set(python_blacklist + nodejs_blacklist))
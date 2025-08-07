install:
	echo "🚀 Creating virtual environment using uv"
	uv sync
	uv run pre-commit install

check:
	echo "🚀 Checking lock file consistency with 'pyproject.toml'"
	uv lock --locked
	echo "🚀 Linting code: Running pre-commit"
	uv run pre-commit run -a
	echo "🚀 Static type checking: Running ty"
	uv run ty check
	echo "🚀 Checking for obsolete dependencies: Running deptry"
	uv run deptry .

test:
	echo "🚀 Testing code: Running pytest"
	uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml

build:
	echo "🚀 Creating wheel file"
	uvx --from build pyproject-build --installer uv

clean:
	echo "🚀 Removing build artifacts"
	uv run python -c "import shutil; import os; shutil.rmtree('dist') if os.path.exists('dist') else None"

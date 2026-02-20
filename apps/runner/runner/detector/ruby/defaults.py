"""Default commands for Ruby project types."""

INSTALL_CMD = "bundle install"

# Test command per detected framework
FRAMEWORK_TEST_CMDS: dict[str, str] = {
    "rails": "bundle exec rails test",
}

# Default test command when rspec is detected or no framework is known
DEFAULT_TEST_CMD = "bundle exec rspec"

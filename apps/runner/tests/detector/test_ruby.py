"""Tests for the Ruby ecosystem detector.

All tests use in-memory fixtures written to tmp_path — no real repos cloned.
"""

from pathlib import Path

import pytest

from runner.detector.ruby import detect_ruby
from runner.detector.ruby.gemfile import detect_framework, detect_test_framework
from runner.detector.orchestrator import detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gemfile(tmp_path: Path, content: str) -> Path:
    (tmp_path / "Gemfile").write_text(content, encoding="utf-8")
    return tmp_path


RAILS_GEMFILE = """\
source 'https://rubygems.org'

gem 'rails', '~> 7.1'
gem 'pg', '~> 1.5'
gem 'puma', '~> 6.4'
gem 'redis', '~> 5.0'

group :development, :test do
  gem 'rspec-rails', '~> 6.0'
  gem 'factory_bot_rails'
end
"""

SINATRA_GEMFILE = """\
source 'https://rubygems.org'

gem 'sinatra', '~> 3.0'
gem 'sinatra-contrib'
gem 'puma'

group :test do
  gem 'rspec', '~> 3.12'
  gem 'rack-test'
end
"""

GRAPE_GEMFILE = """\
source 'https://rubygems.org'

gem 'grape', '~> 1.8'
gem 'grape-entity'
gem 'rack-cors'
"""

HANAMI_GEMFILE = """\
source 'https://rubygems.org'

gem 'hanami', '~> 2.1'
gem 'hanami-router'
gem 'puma'
"""

MINIMAL_GEMFILE = """\
source 'https://rubygems.org'

gem 'json'
gem 'faraday'
"""

MINITEST_RAILS_GEMFILE = """\
source 'https://rubygems.org'

gem 'rails', '~> 7.1'
gem 'pg'

group :test do
  gem 'minitest'
end
"""


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

class TestGemfileFrameworkDetection:
    def test_rails_detected(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.framework == "rails"
        assert result.language == "ruby"

    def test_sinatra_detected(self, tmp_path):
        _gemfile(tmp_path, SINATRA_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.framework == "sinatra"

    def test_grape_detected(self, tmp_path):
        _gemfile(tmp_path, GRAPE_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.framework == "grape"

    def test_hanami_detected(self, tmp_path):
        _gemfile(tmp_path, HANAMI_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.framework == "hanami"

    def test_no_framework_returns_ruby_generic(self, tmp_path):
        _gemfile(tmp_path, MINIMAL_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.framework == "ruby"
        assert result.language == "ruby"

    def test_framework_signal_confidence_is_high(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        signal = detect_framework(tmp_path)
        assert signal is not None
        assert signal.confidence >= 0.9

    def test_comment_lines_are_ignored(self, tmp_path):
        content = """\
# This is a comment: gem 'rails'
source 'https://rubygems.org'
gem 'sinatra'
"""
        _gemfile(tmp_path, content)
        result = detect_ruby(tmp_path)
        assert result.framework == "sinatra"

    def test_double_quoted_gems_are_detected(self, tmp_path):
        content = 'source "https://rubygems.org"\ngem "rails", "~> 7.0"\n'
        _gemfile(tmp_path, content)
        result = detect_ruby(tmp_path)
        assert result.framework == "rails"


# ---------------------------------------------------------------------------
# Test framework / test command detection
# ---------------------------------------------------------------------------

class TestTestCommandDetection:
    def test_rspec_rails_uses_rspec_command(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.test_cmd == "bundle exec rspec"

    def test_minitest_gem_uses_rails_test_command(self, tmp_path):
        _gemfile(tmp_path, MINITEST_RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.test_cmd == "bundle exec rails test"

    def test_plain_rspec_uses_rspec_command(self, tmp_path):
        _gemfile(tmp_path, SINATRA_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.test_cmd == "bundle exec rspec"

    def test_no_test_gem_falls_back_to_default(self, tmp_path):
        _gemfile(tmp_path, GRAPE_GEMFILE)  # no rspec or minitest
        result = detect_ruby(tmp_path)
        assert result.test_cmd == "bundle exec rspec"  # DEFAULT_TEST_CMD


# ---------------------------------------------------------------------------
# Package manager and install command
# ---------------------------------------------------------------------------

class TestDefaultCommands:
    def test_package_manager_is_always_bundler(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.package_manager == "bundler"

    def test_install_cmd_is_bundle_install(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.install_cmd == "bundle install"

    def test_confidence_is_positive(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect_ruby(tmp_path)
        assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# Orchestrator routing
# ---------------------------------------------------------------------------

class TestOrchestratorRouting:
    def test_gemfile_routes_to_ruby_detector(self, tmp_path):
        _gemfile(tmp_path, RAILS_GEMFILE)
        result = detect(tmp_path)
        assert result.language == "ruby"

    def test_gemfile_takes_priority_over_package_json(self, tmp_path):
        """A repo with both Gemfile and package.json should be detected as Ruby."""
        _gemfile(tmp_path, RAILS_GEMFILE)
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"next": "14.0.0"}}', encoding="utf-8"
        )
        result = detect(tmp_path)
        assert result.language == "ruby"
        assert result.framework == "rails"

    def test_python_project_not_routed_to_ruby(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "myapp"\n', encoding="utf-8"
        )
        result = detect(tmp_path)
        assert result.language == "python"

    def test_no_gemfile_no_ruby_detection(self, tmp_path):
        (tmp_path / "package.json").write_text(
            '{"dependencies": {"express": "4.0.0"}}', encoding="utf-8"
        )
        result = detect(tmp_path)
        assert result.language == "javascript"

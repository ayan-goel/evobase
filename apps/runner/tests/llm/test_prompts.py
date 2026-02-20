"""Tests for the prompt engineering layer.

Verifies that prompts contain the expected keywords, constraints,
and framework-specific content based on DetectionResult inputs.
"""

import pytest
from runner.detector.types import DetectionResult
from runner.llm.prompts.discovery_prompts import analysis_prompt, file_selection_prompt
from runner.llm.prompts.patch_prompts import patch_generation_prompt
from runner.llm.prompts.system_prompts import build_system_prompt


class TestSystemPrompts:
    def _make_detection(self, framework: str = "nextjs") -> DetectionResult:
        return DetectionResult(
            framework=framework,
            package_manager="npm",
            install_cmd="npm install",
            build_cmd="npm run build",
            test_cmd="npm test",
        )

    def test_includes_framework_name(self) -> None:
        prompt = build_system_prompt(self._make_detection("nextjs"))
        assert "Next.js" in prompt or "next" in prompt.lower()

    def test_includes_detected_commands(self) -> None:
        prompt = build_system_prompt(self._make_detection())
        assert "npm install" in prompt
        assert "npm run build" in prompt
        assert "npm test" in prompt

    def test_includes_hard_constraints(self) -> None:
        prompt = build_system_prompt(self._make_detection())
        assert "200" in prompt        # line limit
        assert "5 files" in prompt    # file limit

    def test_forbids_test_files(self) -> None:
        prompt = build_system_prompt(self._make_detection())
        assert "test" in prompt.lower()

    def test_nestjs_focus_included(self) -> None:
        prompt = build_system_prompt(self._make_detection("nestjs"))
        assert "NestJS" in prompt or "N+1" in prompt

    def test_express_focus_included(self) -> None:
        prompt = build_system_prompt(self._make_detection("express"))
        assert "Express" in prompt or "middleware" in prompt

    def test_react_vite_focus_included(self) -> None:
        prompt = build_system_prompt(self._make_detection("react-vite"))
        assert "React" in prompt or "useMemo" in prompt or "memo" in prompt

    def test_generic_focus_when_no_framework(self) -> None:
        detection = DetectionResult(framework=None)
        prompt = build_system_prompt(detection)
        assert "JavaScript" in prompt or "TypeScript" in prompt

    def test_json_output_requirement(self) -> None:
        prompt = build_system_prompt(self._make_detection())
        assert "JSON" in prompt

    def test_reasoning_field_required(self) -> None:
        prompt = build_system_prompt(self._make_detection())
        assert '"reasoning"' in prompt or "reasoning" in prompt


class TestNewFrameworkFocusAreas:
    def _prompt(self, framework: str) -> str:
        return build_system_prompt(DetectionResult(framework=framework))

    def test_vue_focus(self) -> None:
        prompt = self._prompt("vue")
        assert "v-for" in prompt or "computed" in prompt

    def test_nuxt_focus(self) -> None:
        prompt = self._prompt("nuxt")
        assert "Nuxt" in prompt or "ClientOnly" in prompt

    def test_angular_focus(self) -> None:
        prompt = self._prompt("angular")
        assert "OnPush" in prompt or "trackBy" in prompt

    def test_svelte_focus(self) -> None:
        prompt = self._prompt("svelte")
        assert "onDestroy" in prompt or "$:" in prompt

    def test_sveltekit_focus(self) -> None:
        prompt = self._prompt("sveltekit")
        assert "onDestroy" in prompt or "load" in prompt

    def test_fastify_focus(self) -> None:
        prompt = self._prompt("fastify")
        assert "schema" in prompt or "Fastify" in prompt

    def test_koa_uses_generic_node(self) -> None:
        prompt = self._prompt("koa")
        assert "event loop" in prompt.lower() or "Node.js" in prompt

    def test_hapi_uses_generic_node(self) -> None:
        prompt = self._prompt("hapi")
        assert "event loop" in prompt.lower() or "Node.js" in prompt

    def test_gatsby_uses_react_focus(self) -> None:
        prompt = self._prompt("gatsby")
        assert "React.memo" in prompt or "useMemo" in prompt

    def test_remix_uses_react_focus(self) -> None:
        prompt = self._prompt("remix")
        assert "React.memo" in prompt or "useMemo" in prompt

    # Ruby / Rails
    def test_rails_focus(self) -> None:
        prompt = self._prompt("rails")
        assert "includes" in prompt or "N+1" in prompt

    def test_grape_uses_rails_focus(self) -> None:
        prompt = self._prompt("grape")
        assert "Active Record" in prompt or "N+1" in prompt

    def test_sinatra_uses_rails_focus(self) -> None:
        prompt = self._prompt("sinatra")
        assert "counter_cache" in prompt or "Rails.cache" in prompt

    def test_ruby_generic_uses_rails_focus(self) -> None:
        prompt = self._prompt("ruby")
        assert "bundle exec" in prompt.lower() or "Rails" in prompt or "N+1" in prompt

    # JVM / Spring Boot
    def test_spring_boot_focus(self) -> None:
        prompt = self._prompt("spring-boot")
        assert "Transactional" in prompt or "JPA" in prompt

    def test_spring_webflux_uses_springboot_focus(self) -> None:
        prompt = self._prompt("spring-webflux")
        assert "Transactional" in prompt or "RestTemplate" in prompt

    def test_quarkus_uses_generic_jvm_focus(self) -> None:
        prompt = self._prompt("quarkus")
        assert "Optional" in prompt or "allocation" in prompt.lower()

    def test_micronaut_uses_generic_jvm_focus(self) -> None:
        prompt = self._prompt("micronaut")
        assert "Optional" in prompt or "allocation" in prompt.lower()

    def test_java_generic_uses_generic_jvm_focus(self) -> None:
        prompt = self._prompt("java")
        assert "HashSet" in prompt or "allocation" in prompt.lower()


class TestDiscoveryPrompts:
    def test_file_selection_requests_json(self) -> None:
        prompt = file_selection_prompt("tree content")
        assert "JSON" in prompt or "json" in prompt.lower()

    def test_file_selection_includes_repo_map(self) -> None:
        prompt = file_selection_prompt("my_repo_tree_content")
        assert "my_repo_tree_content" in prompt

    def test_file_selection_requests_files_key(self) -> None:
        prompt = file_selection_prompt("tree")
        assert '"files"' in prompt

    def test_file_selection_mentions_skip_dirs(self) -> None:
        prompt = file_selection_prompt("tree")
        assert "node_modules" in prompt

    def test_analysis_prompt_includes_file_path(self) -> None:
        prompt = analysis_prompt("src/utils.ts", "const x = 1;")
        assert "src/utils.ts" in prompt

    def test_analysis_prompt_includes_content(self) -> None:
        prompt = analysis_prompt("src/foo.ts", "const sentinel_value = true;")
        assert "sentinel_value" in prompt

    def test_analysis_prompt_defines_opportunity_fields(self) -> None:
        prompt = analysis_prompt("f.ts", "code")
        assert "rationale" in prompt
        assert "approach" in prompt
        assert "risk_level" in prompt

    def test_analysis_prompt_lists_valid_types(self) -> None:
        prompt = analysis_prompt("f.ts", "code")
        assert "performance" in prompt
        assert "tech_debt" in prompt

    def test_analysis_prompt_requests_reasoning(self) -> None:
        prompt = analysis_prompt("f.ts", "code")
        assert "reasoning" in prompt


class TestPatchPrompts:
    def _make_prompt(self) -> str:
        return patch_generation_prompt(
            file_path="src/handler.ts",
            content="function foo() { return 1; }",
            opportunity_type="performance",
            rationale="Regex created in loop",
            approach="Hoist regex to module scope",
            risk_level="low",
        )

    def test_includes_file_path(self) -> None:
        prompt = self._make_prompt()
        assert "src/handler.ts" in prompt

    def test_includes_opportunity_type(self) -> None:
        prompt = self._make_prompt()
        assert "performance" in prompt

    def test_includes_rationale(self) -> None:
        prompt = self._make_prompt()
        assert "Regex created in loop" in prompt

    def test_includes_approach(self) -> None:
        prompt = self._make_prompt()
        assert "Hoist regex" in prompt

    def test_includes_file_content(self) -> None:
        prompt = self._make_prompt()
        assert "function foo()" in prompt

    def test_mentions_line_limit(self) -> None:
        prompt = self._make_prompt()
        assert "200" in prompt

    def test_mentions_file_limit(self) -> None:
        prompt = self._make_prompt()
        assert "5 files" in prompt

    def test_forbids_test_modification(self) -> None:
        prompt = self._make_prompt()
        assert "test" in prompt.lower()

    def test_diff_format_specified(self) -> None:
        prompt = self._make_prompt()
        assert "patch -p1" in prompt or "unified diff" in prompt.lower()

    def test_requests_reasoning_field(self) -> None:
        prompt = self._make_prompt()
        assert '"reasoning"' in prompt

    def test_requests_diff_field(self) -> None:
        prompt = self._make_prompt()
        assert '"diff"' in prompt

    def test_requests_explanation_field(self) -> None:
        prompt = self._make_prompt()
        assert '"explanation"' in prompt

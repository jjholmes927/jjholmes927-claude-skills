#!/usr/bin/env python3
"""
Claude Code Skill: Guideline Refresher
Analyzes codebase evolution and updates guidelines automatically
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import re
import argparse


class GuidelineRefresher:
    def __init__(self, area, config_path=None):
        self.area = area
        self.repo_root = self._find_repo_root()
        self.config = self._load_config(config_path)
        self.findings = defaultdict(list)
        self.metrics = Counter()

    def _find_repo_root(self):
        """Find git repository root"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            print("Error: Not in a git repository")
            sys.exit(1)

    def _load_config(self, config_path):
        """Load skill configuration"""
        if config_path is None:
            config_path = Path(__file__).parent / 'config.json'

        if not config_path.exists():
            # Return default config
            return {
                "analysis_depth": {
                    "quick": {
                        "pr_limit": 20,
                        "commit_days": 30,
                        "min_pattern_frequency": 3
                    },
                    "standard": {
                        "pr_limit": 50,
                        "commit_days": 90,
                        "min_pattern_frequency": 5
                    },
                    "deep": {
                        "pr_limit": 100,
                        "commit_days": 180,
                        "min_pattern_frequency": 3
                    }
                },
                "output_format": {
                    "guidelines_file": ".claude/guidelines/{area}.md",
                    "report_file": ".claude/reports/guideline-refresh-{date}.md",
                    "backup_previous": True
                }
            }

        with open(config_path) as f:
            return json.load(f)

    def analyze_git_history(self, since_days=90):
        """Analyze git commits in the specified area"""
        print(f"  Analyzing last {since_days} days of git history...")

        since_date = (datetime.now() - timedelta(days=since_days)).strftime('%Y-%m-%d')

        # Get commits for this area
        cmd = [
            'git', 'log',
            f'--since={since_date}',
            '--oneline',
            '--', self.area
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                check=True
            )
            commits = [line for line in result.stdout.strip().split('\n') if line]

            self.metrics['total_commits'] = len(commits)

            # Analyze commit messages
            for commit in commits:
                message = commit.split(' ', 1)[1] if ' ' in commit else commit
                message_lower = message.lower()

                # Track refactoring activity
                if any(keyword in message_lower for keyword in ['refactor', 'improve', 'update', 'migrate', 'modernize']):
                    self.findings['refactor_commits'].append({
                        'message': message,
                        'type': 'refactor'
                    })

                # Track technology mentions
                tech_keywords = {
                    'typescript': ['typescript', 'ts', '.tsx'],
                    'react': ['react', 'jsx', 'hook', 'component'],
                    'vue': ['vue', 'composition', 'vue3'],
                    'testing': ['test', 'spec', 'jest', 'vitest', 'cypress'],
                    'async': ['async', 'await', 'promise'],
                    'performance': ['performance', 'optimize', 'lazy', 'memo']
                }

                for tech, keywords in tech_keywords.items():
                    if any(kw in message_lower for kw in keywords):
                        self.metrics[f'tech_{tech}'] += 1

            print(f"    Found {len(commits)} commits")

        except subprocess.CalledProcessError as e:
            print(f"    Warning: Git log failed: {e}")
            self.metrics['total_commits'] = 0

    def analyze_pr_reviews(self, pr_limit=50):
        """Analyze PR reviews for the area using gh CLI"""
        print(f"  Analyzing up to {pr_limit} merged PRs...")

        # Check if gh CLI is available
        try:
            subprocess.run(['gh', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("    Warning: gh CLI not found. Skipping PR analysis.")
            print("    Install with: brew install gh")
            return

        # Get merged PRs
        cmd = [
            'gh', 'pr', 'list',
            '--state', 'merged',
            '--limit', str(pr_limit),
            '--json', 'number,title,body,reviews,files'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_root,
                check=True
            )

            prs = json.loads(result.stdout)

            # Filter PRs that touch our area
            relevant_prs = []
            for pr in prs:
                files = pr.get('files', [])
                if any(self.area in f.get('path', '') for f in files):
                    relevant_prs.append(pr)

            self.metrics['relevant_prs'] = len(relevant_prs)
            print(f"    Found {len(relevant_prs)} PRs touching {self.area}")

            # Extract review patterns
            review_themes = Counter()

            for pr in relevant_prs:
                pr_title = pr.get('title', '').lower()
                pr_body = pr.get('body', '').lower() if pr.get('body') else ''

                # Analyze PR title and body for themes
                combined_text = f"{pr_title} {pr_body}"

                for review in pr.get('reviews', []):
                    body = review.get('body', '')
                    if not body:
                        continue

                    body_lower = body.lower()

                    # Identify themes
                    theme_patterns = {
                        'code_organization': ['structure', 'organize', 'directory', 'folder', 'separate', 'split'],
                        'type_safety': ['type', 'typescript', 'interface', 'any', 'unknown'],
                        'testing': ['test', 'coverage', 'jest', 'spec', 'unit test', 'integration test'],
                        'performance': ['performance', 'optimize', 'slow', 'cache', 'memo', 'lazy'],
                        'error_handling': ['error', 'exception', 'catch', 'try', 'throw'],
                        'naming': ['naming', 'rename', 'name is', 'called', 'variable name'],
                        'documentation': ['document', 'comment', 'readme', 'docs', 'jsdoc'],
                        'accessibility': ['accessibility', 'a11y', 'aria', 'screen reader']
                    }

                    for theme, patterns in theme_patterns.items():
                        if any(pattern in body_lower for pattern in patterns):
                            review_themes[theme] += 1
                            # Store sample feedback (truncated)
                            if len(self.findings[f'{theme}_feedback']) < 5:
                                self.findings[f'{theme}_feedback'].append(body[:300])

            self.findings['review_themes'] = dict(review_themes.most_common(10))

            if review_themes:
                print(f"    Top review themes: {', '.join([f'{k} ({v})' for k, v in review_themes.most_common(3)])}")

        except subprocess.CalledProcessError as e:
            print(f"    Warning: gh CLI failed: {e.stderr if e.stderr else str(e)}")
            print("    Make sure you're authenticated: gh auth login")
        except json.JSONDecodeError as e:
            print(f"    Warning: Failed to parse PR data: {e}")

    def analyze_file_patterns(self):
        """Analyze file structure patterns in the area"""
        print(f"  Analyzing file patterns in {self.area}...")

        area_path = self.repo_root / self.area

        if not area_path.exists():
            print(f"    Warning: Area path {area_path} does not exist")
            return

        # Count file types
        file_types = Counter()
        total_files = 0

        for file_path in area_path.rglob('*'):
            # Skip hidden files and directories
            if any(part.startswith('.') for part in file_path.parts):
                continue

            if file_path.is_file():
                total_files += 1
                suffix = file_path.suffix
                if suffix:
                    file_types[suffix] += 1

        self.findings['file_types'] = dict(file_types.most_common(10))
        self.metrics['total_files'] = total_files

        print(f"    Found {total_files} files")

        # Analyze naming conventions for code files
        code_extensions = {'.ts', '.tsx', '.js', '.jsx', '.py', '.java', '.go', '.rs'}
        naming_patterns = defaultdict(int)

        for file_path in area_path.rglob('*'):
            if file_path.suffix in code_extensions and file_path.is_file():
                name = file_path.stem

                # Skip index files
                if name.lower() in ['index', '__init__']:
                    continue

                # Detect naming patterns
                if name[0].isupper() and not '_' in name and not '-' in name:
                    naming_patterns['PascalCase'] += 1
                elif '_' in name and name.islower():
                    naming_patterns['snake_case'] += 1
                elif '-' in name and name.islower():
                    naming_patterns['kebab-case'] += 1
                elif name[0].islower() and not '_' in name and not '-' in name:
                    naming_patterns['camelCase'] += 1
                else:
                    naming_patterns['mixed'] += 1

        if naming_patterns:
            self.findings['naming_conventions'] = dict(naming_patterns)
            dominant = max(naming_patterns.items(), key=lambda x: x[1])
            print(f"    Dominant naming: {dominant[0]} ({dominant[1]} files)")

    def load_current_guidelines(self):
        """Load existing guidelines for this area"""
        # Normalize area name for filename
        filename = self.area.replace('/', '_').replace('\\', '_')
        guidelines_path = self.repo_root / f".claude/guidelines/{filename}.md"

        if guidelines_path.exists():
            with open(guidelines_path) as f:
                return f.read()
        return None

    def generate_updated_guidelines(self):
        """Generate updated guidelines based on analysis"""
        current = self.load_current_guidelines()

        guidelines = f"""# Coding Guidelines: {self.area}

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Auto-generated by:** Guideline Refresher Skill
**Analysis Period:** {self.config['analysis_depth']} configuration

## Analysis Summary

- **Total commits analyzed:** {self.metrics.get('total_commits', 0)}
- **Relevant PRs reviewed:** {self.metrics.get('relevant_prs', 0)}
- **Files in area:** {self.metrics.get('total_files', 0)}

"""

        # Add technology focus
        tech_metrics = [(k.replace('tech_', ''), v) for k, v in self.metrics.items() if k.startswith('tech_')]
        if tech_metrics:
            guidelines += "## Technology Focus\n\n"
            guidelines += "Based on commit message analysis:\n\n"
            for tech, count in sorted(tech_metrics, key=lambda x: x[1], reverse=True):
                if count >= 3:  # Only show significant mentions
                    guidelines += f"- **{tech.title()}**: {count} commits\n"
            guidelines += "\n"

        # Add file organization
        if 'file_types' in self.findings and self.findings['file_types']:
            guidelines += "## File Organization\n\n"
            guidelines += "**Primary file types:**\n\n"
            for ftype, count in list(self.findings['file_types'].items())[:5]:
                percentage = (count / self.metrics['total_files'] * 100) if self.metrics['total_files'] > 0 else 0
                guidelines += f"- `{ftype}`: {count} files ({percentage:.1f}%)\n"
            guidelines += "\n"

        # Add naming conventions
        if 'naming_conventions' in self.findings and self.findings['naming_conventions']:
            guidelines += "## Naming Conventions\n\n"
            guidelines += "**Observed naming patterns:**\n\n"

            total_named = sum(self.findings['naming_conventions'].values())
            for pattern, count in sorted(self.findings['naming_conventions'].items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_named * 100) if total_named > 0 else 0
                guidelines += f"- **{pattern}**: {count} files ({percentage:.1f}%)\n"

            dominant = max(self.findings['naming_conventions'].items(), key=lambda x: x[1])
            guidelines += f"\n**Recommendation:** Follow `{dominant[0]}` pattern (dominant in {dominant[1]} files)\n\n"

        # Add code review focus areas
        if 'review_themes' in self.findings and self.findings['review_themes']:
            guidelines += "## Code Review Focus Areas\n\n"
            guidelines += "Based on recurring themes in PR reviews:\n\n"

            for theme, count in list(self.findings['review_themes'].items())[:5]:
                theme_display = theme.replace('_', ' ').title()
                guidelines += f"### {theme_display} ({count} mentions)\n\n"

                # Add sample feedback if available
                feedback_key = f'{theme}_feedback'
                if feedback_key in self.findings and self.findings[feedback_key]:
                    sample = self.findings[feedback_key][0]
                    # Clean and truncate
                    sample = sample.replace('\n', ' ').strip()
                    if len(sample) > 200:
                        sample = sample[:200] + "..."
                    guidelines += f"Example feedback: \"{sample}\"\n\n"

        # Add recent patterns
        if self.findings.get('refactor_commits'):
            guidelines += "## Recent Evolution\n\n"
            guidelines += "**Recent refactoring themes:**\n\n"

            # Group similar refactoring messages
            refactor_types = defaultdict(list)
            for commit in self.findings['refactor_commits'][:10]:
                msg = commit['message']
                # Simple categorization
                if 'typescript' in msg.lower() or 'type' in msg.lower():
                    refactor_types['TypeScript Migration'].append(msg)
                elif 'test' in msg.lower():
                    refactor_types['Testing Improvements'].append(msg)
                elif 'component' in msg.lower() or 'react' in msg.lower():
                    refactor_types['Component Refactoring'].append(msg)
                else:
                    refactor_types['General Improvements'].append(msg)

            for category, messages in refactor_types.items():
                guidelines += f"**{category}** ({len(messages)} commits):\n"
                for msg in messages[:3]:  # Show top 3
                    guidelines += f"- {msg}\n"
                guidelines += "\n"

        # Add specific recommendations
        recommendations = self._generate_recommendations()
        if recommendations:
            guidelines += "## Recommendations\n\n"
            guidelines += "Based on the analysis above:\n\n"
            for i, rec in enumerate(recommendations, 1):
                guidelines += f"{i}. {rec}\n"
            guidelines += "\n"

        # Add placeholder for code examples
        guidelines += "## Code Examples\n\n"
        guidelines += "> **Note:** Add specific code examples from recent merged PRs that demonstrate the recommended patterns.\n\n"

        # Compare with current guidelines if they exist
        if current:
            guidelines += "## Changes from Previous Guidelines\n\n"
            comparison = self._compare_guidelines(current)
            guidelines += comparison + "\n"
        else:
            guidelines += "## Changes from Previous Guidelines\n\n"
            guidelines += "*This is the first version of guidelines for this area.*\n\n"

        # Add metadata
        guidelines += "---\n\n"
        guidelines += "*These guidelines are automatically generated based on actual codebase patterns. "
        guidelines += "Review and enhance with code examples and project-specific context.*\n"

        return guidelines

    def _generate_recommendations(self):
        """Generate specific recommendations based on findings"""
        recommendations = []

        # TypeScript recommendation
        ts_mentions = self.metrics.get('tech_typescript', 0)
        if ts_mentions > 10:
            recommendations.append(
                "**Strong TypeScript usage detected.** Enforce strict type checking and avoid `any` types. "
                "Consider enabling `strictNullChecks` and `noImplicitAny` in tsconfig.json."
            )
        elif ts_mentions > 5:
            recommendations.append(
                "**TypeScript adoption in progress.** Continue migrating JavaScript files to TypeScript. "
                "Define interfaces for all props and function parameters."
            )

        # Testing recommendation
        test_mentions = self.metrics.get('tech_testing', 0)
        test_theme = self.findings.get('review_themes', {}).get('testing', 0)

        if test_theme > 5 or test_mentions > 8:
            recommendations.append(
                "**Testing is a priority.** Ensure all new code includes tests. "
                "PR reviews frequently mention testing - make it a first-class concern."
            )

        # Performance recommendation
        perf_theme = self.findings.get('review_themes', {}).get('performance', 0)
        if perf_theme > 3:
            recommendations.append(
                "**Performance optimization is a recurring theme.** Profile before optimizing. "
                "Consider React.memo, useMemo, and code splitting for large components."
            )

        # Code organization recommendation
        org_theme = self.findings.get('review_themes', {}).get('code_organization', 0)
        if org_theme > 5:
            recommendations.append(
                "**Code organization is frequently discussed.** Follow established file structure patterns. "
                "Keep related files together and maintain consistent directory organization."
            )

        # Error handling recommendation
        error_theme = self.findings.get('review_themes', {}).get('error_handling', 0)
        if error_theme > 3:
            recommendations.append(
                "**Error handling needs attention.** Implement consistent error handling patterns. "
                "Use try-catch blocks, provide meaningful error messages, and handle edge cases."
            )

        # React-specific
        react_mentions = self.metrics.get('tech_react', 0)
        if react_mentions > 10:
            recommendations.append(
                "**React patterns are dominant.** Use functional components with hooks. "
                "Avoid class components for new code. Follow React best practices for state management."
            )

        return recommendations

    def _compare_guidelines(self, old_guidelines):
        """Compare old and new guidelines"""
        comparison = ""

        # Extract sections from both
        old_sections = set(re.findall(r'^## (.+)$', old_guidelines, re.MULTILINE))
        new_guidelines_text = self.generate_updated_guidelines()
        new_sections = set(re.findall(r'^## (.+)$', new_guidelines_text, re.MULTILINE))

        added = new_sections - old_sections
        removed = old_sections - new_sections
        common = old_sections & new_sections

        if added:
            comparison += "**New sections:**\n"
            for section in sorted(added):
                comparison += f"- {section}\n"
            comparison += "\n"

        if removed:
            comparison += "**Removed sections:**\n"
            for section in sorted(removed):
                comparison += f"- {section}\n"
            comparison += "\n"

        if common:
            comparison += f"**Updated sections:** {len(common)} sections refined based on recent activity\n\n"

        if not added and not removed:
            comparison += "Guidelines structure maintained, content updated based on recent patterns.\n"

        # Compare metrics if present in old guidelines
        old_commit_match = re.search(r'Total commits analyzed:\*\* (\d+)', old_guidelines)
        if old_commit_match:
            old_commits = int(old_commit_match.group(1))
            new_commits = self.metrics.get('total_commits', 0)
            comparison += f"\n**Data freshness:** Analyzed {new_commits} recent commits (previous: {old_commits})\n"

        return comparison

    def save_guidelines(self, guidelines):
        """Save updated guidelines to file"""
        guidelines_dir = self.repo_root / ".claude/guidelines"
        guidelines_dir.mkdir(parents=True, exist_ok=True)

        # Normalize area name for filename
        filename = self.area.replace('/', '_').replace('\\', '_')
        output_path = guidelines_dir / f"{filename}.md"

        # Backup existing
        if output_path.exists() and self.config['output_format'].get('backup_previous', True):
            backup_name = f"{filename}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.md.bak"
            backup_path = guidelines_dir / backup_name
            output_path.rename(backup_path)
            print(f"  Backed up previous version to: {backup_path.name}")

        # Save new guidelines
        with open(output_path, 'w') as f:
            f.write(guidelines)

        print(f"✓ Guidelines saved to: {output_path.relative_to(self.repo_root)}")
        return output_path

    def generate_report(self):
        """Generate analysis report"""
        report_dir = self.repo_root / ".claude/reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = report_dir / f"guideline-refresh-{timestamp}.md"

        report = f"""# Guideline Refresh Report

**Area:** `{self.area}`
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Analysis Depth:** {self._get_depth_from_config()}

## Executive Summary

This report documents the analysis performed to refresh coding guidelines for `{self.area}`.

## Metrics

"""

        # Format metrics nicely
        metric_categories = {
            'Volume': ['total_commits', 'relevant_prs', 'total_files'],
            'Technology': [k for k in self.metrics.keys() if k.startswith('tech_')]
        }

        for category, metric_keys in metric_categories.items():
            report += f"### {category}\n\n"
            for key in metric_keys:
                if key in self.metrics:
                    display_name = key.replace('_', ' ').replace('tech ', '').title()
                    report += f"- **{display_name}:** {self.metrics[key]}\n"
            report += "\n"

        # Add findings
        if self.findings:
            report += "## Key Findings\n\n"

            # Review themes
            if 'review_themes' in self.findings:
                report += "### PR Review Themes\n\n"
                report += "Most frequently mentioned topics in code reviews:\n\n"
                for theme, count in sorted(
                    self.findings['review_themes'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    report += f"- **{theme.replace('_', ' ').title()}**: {count} mentions\n"
                report += "\n"

            # File patterns
            if 'file_types' in self.findings:
                report += "### File Type Distribution\n\n"
                for ftype, count in list(self.findings['file_types'].items())[:5]:
                    report += f"- `{ftype}`: {count} files\n"
                report += "\n"

            # Naming conventions
            if 'naming_conventions' in self.findings:
                report += "### Naming Conventions\n\n"
                for pattern, count in sorted(
                    self.findings['naming_conventions'].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    report += f"- **{pattern}**: {count} files\n"
                report += "\n"

            # Refactoring activity
            if 'refactor_commits' in self.findings and self.findings['refactor_commits']:
                report += "### Recent Refactoring Activity\n\n"
                report += f"Found {len(self.findings['refactor_commits'])} refactoring-related commits:\n\n"
                for commit in self.findings['refactor_commits'][:5]:
                    report += f"- {commit['message']}\n"
                report += "\n"

        # Add sample review feedback
        feedback_sections = [k for k in self.findings.keys() if k.endswith('_feedback')]
        if feedback_sections:
            report += "## Sample Review Feedback\n\n"
            for section in feedback_sections[:3]:  # Top 3 categories
                theme = section.replace('_feedback', '').replace('_', ' ').title()
                samples = self.findings[section][:2]  # Top 2 samples

                if samples:
                    report += f"### {theme}\n\n"
                    for sample in samples:
                        clean_sample = sample.replace('\n', ' ').strip()
                        if len(clean_sample) > 250:
                            clean_sample = clean_sample[:250] + "..."
                        report += f"> {clean_sample}\n\n"

        # Add conclusion
        report += "## Next Steps\n\n"
        report += "1. Review the generated guidelines in `.claude/guidelines/`\n"
        report += "2. Add specific code examples from recent merged PRs\n"
        report += "3. Validate recommendations align with project standards\n"
        report += "4. Share with team for feedback\n"
        report += "5. Commit updated guidelines to version control\n\n"

        report += "---\n\n"
        report += "*Report generated by Guideline Refresher Skill*\n"

        with open(report_path, 'w') as f:
            f.write(report)

        print(f"✓ Report saved to: {report_path.relative_to(self.repo_root)}")
        return report_path

    def _get_depth_from_config(self):
        """Determine which depth config was used"""
        # This is a simplified version - could be enhanced
        commit_count = self.metrics.get('total_commits', 0)

        if commit_count > 0:
            return "standard"  # Default assumption
        return "unknown"

    def run(self, depth='standard'):
        """Run the complete analysis"""
        if depth not in self.config['analysis_depth']:
            print(f"Error: Invalid depth '{depth}'. Choose from: {list(self.config['analysis_depth'].keys())}")
            sys.exit(1)

        config = self.config['analysis_depth'][depth]

        print(f"\n🔍 Guideline Refresher")
        print(f"   Area: {self.area}")
        print(f"   Depth: {depth}")
        print(f"   Repo: {self.repo_root}")
        print()

        # Run analysis phases
        self.analyze_git_history(since_days=config['commit_days'])
        self.analyze_pr_reviews(pr_limit=config['pr_limit'])
        self.analyze_file_patterns()

        print()
        print("→ Generating updated guidelines...")
        guidelines = self.generate_updated_guidelines()

        print("→ Saving guidelines...")
        guidelines_path = self.save_guidelines(guidelines)

        print("→ Generating report...")
        report_path = self.generate_report()

        print()
        print("✅ Guideline refresh complete!")
        print()
        print(f"📄 Guidelines: {guidelines_path.relative_to(self.repo_root)}")
        print(f"📊 Report: {report_path.relative_to(self.repo_root)}")
        print()

        return {
            'guidelines_path': str(guidelines_path),
            'report_path': str(report_path),
            'metrics': dict(self.metrics),
            'findings': {k: v for k, v in self.findings.items() if not k.endswith('_feedback')}
        }


def main():
    parser = argparse.ArgumentParser(
        description='Refresh coding guidelines for a codebase area',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --area frontend/components
  %(prog)s --area backend/api --depth deep
  %(prog)s --area utils/helpers --depth quick
        """
    )

    parser.add_argument(
        '--area',
        required=True,
        help='Area of codebase to analyze (e.g., frontend/components, backend/api)'
    )
    parser.add_argument(
        '--depth',
        default='standard',
        choices=['quick', 'standard', 'deep'],
        help='Analysis depth: quick (30 days), standard (90 days), deep (180 days)'
    )
    parser.add_argument(
        '--config',
        help='Path to custom config file (optional)'
    )

    args = parser.parse_args()

    try:
        refresher = GuidelineRefresher(args.area, args.config)
        result = refresher.run(depth=args.depth)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

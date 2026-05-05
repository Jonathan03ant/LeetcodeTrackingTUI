"""
Fetch LeetCode problem descriptions using GraphQL API
"""

import requests
import re
from typing import Optional, Dict


def extract_problem_slug(url: str) -> Optional[str]:
    """Extract problem slug from LeetCode URL"""
    # https://leetcode.com/problems/two-sum/ -> two-sum
    match = re.search(r'/problems/([^/]+)', url)
    return match.group(1) if match else None


def fetch_problem_description(url: str) -> Optional[Dict[str, str]]:
    """
    Fetch problem description from LeetCode using GraphQL API

    Returns dict with:
        - title: Problem title
        - description: Problem description (HTML converted to text)
        - url: Original URL
    """
    try:
        slug = extract_problem_slug(url)
        if not slug:
            return None

        # LeetCode GraphQL API endpoint
        graphql_url = "https://leetcode.com/graphql"

        # GraphQL query
        query = """
        query getQuestionDetail($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                questionId
                title
                content
                difficulty
                exampleTestcases
            }
        }
        """

        payload = {
            "query": query,
            "variables": {"titleSlug": slug}
        }

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
        }

        response = requests.post(graphql_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        if 'data' in data and data['data']['question']:
            question = data['data']['question']

            # Convert HTML to plain text (simple approach)
            content = question['content']
            # Remove HTML tags
            content = re.sub('<[^<]+?>', '', content)
            # Replace HTML entities
            content = content.replace('&nbsp;', ' ')
            content = content.replace('&lt;', '<')
            content = content.replace('&gt;', '>')
            content = content.replace('&amp;', '&')
            content = content.replace('&quot;', '"')
            # Clean up extra whitespace
            content = re.sub(r'\n\s*\n', '\n\n', content)
            content = content.strip()

            return {
                'title': f"#{question['questionId']}. {question['title']} [{question['difficulty']}]",
                'description': content,
                'url': url
            }

        return None

    except Exception as e:
        # Silently fail - will show fallback in UI
        return None


def format_problem_for_display(problem_data: Dict[str, str], max_lines: int = 30) -> str:
    """Format problem data for terminal display"""
    if not problem_data:
        return "Failed to fetch problem description"

    lines = []
    lines.append(problem_data['title'])
    lines.append("=" * 70)
    lines.append("")

    # Split description into lines and limit
    desc_lines = problem_data['description'].split('\n')
    display_lines = desc_lines[:max_lines]

    lines.extend(display_lines)

    if len(desc_lines) > max_lines:
        lines.append("")
        lines.append(f"... ({len(desc_lines) - max_lines} more lines)")

    return '\n'.join(lines)


if __name__ == "__main__":
    # Test
    url = "https://leetcode.com/problems/two-sum/"
    print(f"Fetching: {url}")
    data = fetch_problem_description(url)
    if data:
        print(format_problem_for_display(data, max_lines=20))
    else:
        print("Failed to fetch")

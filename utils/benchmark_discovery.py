"""Discover URLs with the provider search tool; never treat snippets as evidence."""
from __future__ import annotations

import os
from urllib.parse import urlparse, urldefrag

from anthropic import Anthropic
from utils.llm_client import get_llm_config


def allowed_url(url, domains):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        return (parsed.scheme == 'https' and not parsed.username and parsed.port in (None, 443)
                and any(host == domain or host.endswith('.' + domain) for domain in domains))
    except ValueError:
        return False


def parse_search_response(response, domains):
    urls, queries, errors = [], [], []
    for block in response.get('content', []):
        if block.get('type') == 'server_tool_use' and block.get('name') == 'web_search':
            queries.append(str(block.get('input', {}).get('query', '')))
        if block.get('type') != 'web_search_tool_result':
            continue
        content = block.get('content', [])
        if isinstance(content, dict):
            errors.append(content.get('error_code', 'search_error'))
            continue
        for result in content:
            url = urldefrag(result.get('url', ''))[0]
            if result.get('type') == 'web_search_result' and allowed_url(url, domains) and url not in urls:
                urls.append(url)
    return {'urls': urls[:8], 'queries': queries, 'errors': errors}


def discover(bank, brief, domains):
    if not domains:
        return {'urls': [], 'queries': [], 'errors': ['official_domain_missing']}
    config = get_llm_config()
    with Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'), timeout=90, max_retries=0) as client:
        response = client.messages.create(
            model=config.model,
            max_tokens=1500,
            tools=[{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 2, 'allowed_domains': domains}],
            messages=[{'role': 'user', 'content': (
                f"Web araması yap. {bank} bankasının {brief['segment']} müşterileri için "
                f"{brief['topic']} konusunda resmî ürün, kampanya ve iş ortaklığı sayfalarını bul. "
                f"Kıyas ölçütleri: {', '.join(brief['criteria'])}. "
                f"Ek talimat: {brief.get('instructions', '')}. "
                "En fazla iki arama yap. Yalnızca kaynakları keşfet; fiyat ya da teklif bilgisi üretme."
            )}],
        )
    return parse_search_response(response.model_dump(), domains)

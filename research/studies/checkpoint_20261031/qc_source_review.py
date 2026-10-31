"""Offline, conservative source inspection. Never imports or executes strategy code."""
import ast
from collections import defaultdict
import hashlib
import difflib
from html.parser import HTMLParser
import re
import textwrap


class SourceHTML(HTMLParser):
    """Preserve code whitespace; iframe contents are deliberately never followed."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.current = None
        self.blocks = []
        self.text_parts = []
        self.iframes = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'iframe':
            self.iframes += 1
        if tag in ('pre', 'code'):
            if self.depth == 0:
                self.current = {'language': attrs.get('class', 'unknown'), 'line': self.getpos()[0], 'parts': []}
            self.depth += 1
        if tag == 'br' and self.current:
            self.current['parts'].append('\n')
        if tag in ('p', 'li', 'h2', 'h3'):
            self.text_parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('pre', 'code') and self.depth:
            self.depth -= 1
            if self.depth == 0:
                block = self.current
                block['text'] = ''.join(block.pop('parts'))
                self.blocks.append(block)
                self.current = None

    def handle_data(self, data):
        self.text_parts.append(data)
        if self.current:
            self.current['parts'].append(data)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def code_identity(code):
    """AST identity retains names/constants; syntax failure is not equivalence."""
    code = textwrap.dedent(code).strip()
    result = {'raw_sha256': sha256(code.encode()), 'ast_sha256': None,
              'algorithm_class_candidate': False, 'package_complete': False}
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return result
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            methods = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            if any('QCAlgorithm' in b for b in bases) and methods & {'Initialize', 'initialize'}:
                result['algorithm_class_candidate'] = True
    # Ignore docstrings only, never parameters, literals or variable identifiers.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body = node.body[1:]
    result['ast_sha256'] = sha256(ast.dump(tree, include_attributes=False).encode())
    return result


# These detectors find declarations, NOT verified runtime behavior or data entitlements.
RULES = {
    'equity_prices_and_actions': r'AddEquity|add_equity',
    'point_in_time_fundamentals': r'AddUniverse|add_universe|FineFundamental|FineSelection|fine_selection|EarningReports|ValuationRatios|MarketCap',
    'forex_prices_and_conventions': r'AddForex|add_forex',
    'futures_chains_contracts_and_rolls': r'AddFuture\b|add_future\b|FutureChain|future_chain',
    'option_chains_quotes_expiry_assignment': r'AddOption|add_option|OptionChain|option_chain',
    'crypto_prices_and_market_rules': r'AddCrypto|add_crypto',
    'index_data': r'AddIndex|add_index',
    'custom_or_external_data': r'AddData\b|add_data\b|Download\b|\.download\b|read_csv|Quandl|Fama.?French',
    'historical_warmup': r'\.History\b|\.history\b|SetWarmUp|set_warm_up',
    'monthly_schedule': r'MonthStart|MonthEnd|month_start|month_end',
    'weekly_schedule': r'WeekStart|WeekEnd|week_start|week_end',
    'daily_schedule': r'EveryDay|every_day',
    'margin_account_declaration': r'AccountType\.Margin|AccountType\.MARGIN',
    'leverage_declaration': r'SetLeverage|set_leverage',
}


def inspect_html(body):
    parser = SourceHTML()
    parser.feed(body)
    blocks = []
    for block in parser.blocks:
        code = block['text']
        # Inline API identifiers and boilerplate do not drive similarity assertions.
        meaningful = len(code.splitlines()) >= 5 and len(re.findall(r'\w+|[^\s\w]', code)) >= 50
        blocks.append({**block, **code_identity(code), 'meaningful': meaningful})
    observations = []
    lines = body.splitlines()
    for field, pattern in RULES.items():
        hits = [i for i, line in enumerate(lines, 1) if re.search(pattern, line)]
        if hits:
            observations.append({'field': field, 'lines': hits[:12], 'basis': 'static_method_or_code_declaration'})
    # Preserve only short API declarations; never infer from titles or prose.
    declarations = []
    for block in blocks:
        for line in block['text'].splitlines():
            if re.search(r'\b(?:SetStartDate|SetEndDate|SetLeverage|set_start_date|set_end_date|set_leverage|AddEquity|add_equity|AddForex|add_forex|AddFuture|add_future|AddOption|add_option|AddCrypto|add_crypto|AddIndex|add_index)\s*\(', line):
                declarations.append(line.strip()[:220])
    resolutions = sorted(set(re.findall(r'Resolution\.([A-Za-z_]+)', body)))
    return {'blocks': blocks, 'observations': observations, 'declarations': declarations,
            'resolutions': resolutions, 'iframes': parser.iframes,
            'text': ''.join(parser.text_parts)}


def duplicate_groups(blocks):
    """Compare observed meaningful fragments, not algorithms/packages or return paths."""
    groups = []
    for key in ('raw_sha256', 'ast_sha256'):
        by_hash = defaultdict(list)
        for block in blocks:
            if block['meaningful'] and block[key]:
                by_hash[block[key]].append({k: block[k] for k in ('id', 'path', 'line', 'language')})
        for digest, members in sorted(by_hash.items()):
            if len({m['id'] for m in members}) > 1:
                groups.append({'kind': 'identical_observed_fragment' if key == 'raw_sha256' else 'same_python_AST_fragment',
                               'hash': digest, 'members': members, 'package_equivalence': 'unverified'})
    return groups


def rights(kind):
    licensed = kind == 'tutorial'
    return {
        'acquisition': 'licensed_official_github' if licensed else 'new_site_extraction_blocked_use_licensed_sources_first',
        'code_inspection': 'allowed_for_pinned_repository_artifacts' if licensed else 'source_specific_permission_unknown',
        'modification': 'conditional_Apache_2_0_for_repository_artifacts_only' if licensed else 'unknown',
        'redistribution': 'conditional_Apache_2_0_for_repository_artifacts_only' if licensed else 'unknown',
        'data_cloud_entitlement': 'unverified_per_dataset',
        'data_download': 'separate_license_required_not_established',
        'data_redistribution': 'not_established',
        'other_author_results_republication': 'not_established',
        'external_dependencies_rights': 'not_established',
        'source_package_export': 'blocked_incomplete_package_or_rights',
        'policy_refs': ['APACHE-TUTORIALS', 'QC-ACCESS', 'QC-DATA', 'RESULTS-SEPARATE'],
    }


def similarity_leads(blocks):
    """Lexical leads retain constants and identifiers; never infer a complete fork."""
    candidates = []
    for block in blocks:
        tokens = re.findall(r"\w+|[^\s\w]", block['text'])
        if len(tokens) >= 100:
            candidates.append((block, tokens))
    leads = []
    for i, (a, a_tokens) in enumerate(candidates):
        for b, b_tokens in candidates[i + 1:]:
            if a['id'] == b['id']:
                continue
            matcher = difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
            if matcher.real_quick_ratio() < .8 or matcher.quick_ratio() < .8:
                continue
            score = matcher.ratio()
            if score >= .8:
                leads.append({'kind': 'lexically_similar_fragment_not_proven_fork',
                              'similarity': round(score, 4), 'token_counts': [len(a_tokens), len(b_tokens)],
                              'members': [{k: x[k] for k in ('id', 'path', 'line')} for x in (a, b)],
                              'package_equivalence': 'unverified'})
    return sorted(leads, key=lambda x: -x['similarity'])

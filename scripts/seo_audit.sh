#!/usr/bin/env bash
set -euo pipefail

PUBLIC_DIR="${1:-public}"

if [[ ! -d "$PUBLIC_DIR" ]]; then
  echo "SEO audit failed: directory not found: $PUBLIC_DIR"
  exit 1
fi

failures=0
warnings=0

note_fail() {
  echo "SEO FAIL: $1"
  failures=$((failures + 1))
}

note_warn() {
  echo "SEO WARN: $1"
  warnings=$((warnings + 1))
}

html_files=()
while IFS= read -r f; do
  html_files+=("$f")
done < <(find "$PUBLIC_DIR" -type f -name "*.html" | sort)

if [[ ${#html_files[@]} -eq 0 ]]; then
  note_fail "No HTML files found under $PUBLIC_DIR"
fi

for file in "${html_files[@]}"; do
  is_alias_redirect=0
  if rg -q 'http-equiv=refresh|http-equiv="refresh"' "$file"; then
    is_alias_redirect=1
  fi

  if ! rg -q '<title>[^<]+' "$file"; then
    note_fail "$file missing <title>"
  fi

  if [[ "$is_alias_redirect" -eq 0 ]] && ! rg -q 'meta name="?description"? content=' "$file"; then
    note_fail "$file missing meta description"
  fi

  if ! rg -q 'link rel="?canonical"? href=' "$file"; then
    note_fail "$file missing canonical"
  fi

  if [[ "$is_alias_redirect" -eq 1 ]]; then
    continue
  fi

  if [[ "$file" == *"/404.html" ]]; then
    if ! rg -q 'meta name="?robots"? content="[^"]*noindex[^"]*"' "$file"; then
      note_fail "$file should be noindex"
    fi
  else
    if ! rg -q 'meta name="?robots"? content="[^"]*index[^"]*"' "$file"; then
      note_fail "$file missing indexable robots meta"
    fi
  fi
done

deal_content_files=()
while IFS= read -r f; do
  deal_content_files+=("$f")
done < <(find content/deals -maxdepth 1 -type f -name "*.md" ! -name "_index.md" | sort)

for file in "${deal_content_files[@]}"; do
  if ! rg -q '^summary\s*=\s*".+"' "$file"; then
    note_fail "$file missing required frontmatter: summary"
  fi
  if ! rg -q '^sale_price\s*=\s*[0-9]+' "$file"; then
    note_fail "$file missing required frontmatter: sale_price"
  fi
  if ! rg -q '^list_price\s*=\s*[0-9]+' "$file"; then
    note_fail "$file missing required frontmatter: list_price"
  fi
  if ! rg -q '^time_left\s*=\s*".+"' "$file"; then
    note_fail "$file missing required frontmatter: time_left"
  fi
  if ! rg -q '^image\s*=\s*".+"' "$file"; then
    note_warn "$file missing optional frontmatter for now: image"
  fi
  has_product_url=0
  has_affiliate_url=0
  if rg -q '^product_url\s*=\s*"https?://.+"' "$file"; then
    has_product_url=1
  fi
  if rg -q '^affiliate_url\s*=\s*"https?://.+"' "$file"; then
    has_affiliate_url=1
  fi
  if [[ "$has_product_url" -eq 0 && "$has_affiliate_url" -eq 0 ]]; then
    note_warn "$file has no product_url or affiliate_url yet"
  fi
done

deal_pages=()
while IFS= read -r f; do
  deal_pages+=("$f")
done < <(find "$PUBLIC_DIR/deals" -mindepth 2 -maxdepth 2 -type f -name "index.html" | sort)

for file in "${deal_pages[@]}"; do
  if ! rg -q '"@type":"Product"' "$file"; then
    note_fail "$file missing Product schema"
  fi
  shows_amazon_message=0
  if rg -q 'See Amazon for current price and availability\.' "$file"; then
    shows_amazon_message=1
  fi
  if [[ "$shows_amazon_message" -eq 0 ]] && ! rg -q '"@type":"Offer"' "$file"; then
    note_fail "$file missing Offer schema"
  fi
done

broken_link_failures=0
while IFS= read -r link; do
  clean="${link%%\#*}"
  clean="${clean%%\?*}"
  [[ -z "$clean" ]] && continue

  if [[ "$clean" == "/" ]]; then
    target="$PUBLIC_DIR/index.html"
  elif [[ "$clean" == */ ]]; then
    target="$PUBLIC_DIR${clean}index.html"
  else
    target="$PUBLIC_DIR$clean"
    if [[ ! -f "$target" && ! "$clean" =~ \.[a-zA-Z0-9]+$ ]]; then
      target="$PUBLIC_DIR$clean/index.html"
    fi
  fi

  if [[ ! -f "$target" ]]; then
    echo "SEO FAIL: broken root-relative link target not found: $clean"
    broken_link_failures=$((broken_link_failures + 1))
  fi
done < <(rg -o 'href="/[^"]+"' "$PUBLIC_DIR" -g '*.html' | sed -E 's/.*href="([^"]+)"/\1/' | sort -u)

if [[ "$broken_link_failures" -gt 0 ]]; then
  failures=$((failures + broken_link_failures))
fi

if [[ "$failures" -gt 0 ]]; then
  echo "SEO audit failed with $failures issue(s)."
  exit 1
fi

if [[ "$warnings" -gt 0 ]]; then
  echo "SEO audit passed with $warnings warning(s)."
else
  echo "SEO audit passed."
fi

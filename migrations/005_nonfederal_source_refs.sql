-- Extend only the existing basic-citation projection. Old sealed snapshots and
-- all free-field/scalar/timestamp gates remain unchanged. Reviewed issuer paths
-- are explicit: no directory-wide, generic AHA, or application-portal allowance.
CREATE OR REPLACE FUNCTION rigbys_free_source_refs(refs jsonb) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
SELECT coalesce(jsonb_object_agg(fields.key, allowed.refs), '{}'::jsonb)
FROM jsonb_each(CASE WHEN jsonb_typeof(refs) = 'object' THEN refs ELSE '{}'::jsonb END) AS fields
CROSS JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
        'source', item->'source', 'source_id', item->'source_id',
        'url', item->'url', 'fetched_at', item->'fetched_at')) AS refs
    FROM jsonb_array_elements(CASE WHEN jsonb_typeof(fields.value) = 'array'
                                  THEN fields.value ELSE '[]'::jsonb END) AS item
    WHERE jsonb_typeof(item) = 'object'
      AND jsonb_typeof(item->'source_id') = 'string'
      AND item->>'source_id' ~ '^[A-Za-z0-9_-]{1,200}$'
      AND jsonb_typeof(item->'url') = 'string'
      AND (
          (item->>'source' = 'grants_gov'
           AND item->>'url' ~ '^https://(www\.)?grants\.gov/search-results-detail/[A-Za-z0-9_-]+/?$')
          OR
          (item->>'source' = 'aha' AND (
              item->>'url' ~ '^https://professional\.heart\.org/en/research-programs/aha-funding-opportunities/(career-development-award|innovative-project-award)$'
              OR item->>'url' ~ '^https://professional\.heart\.org/en/-/media/PHD-Files/Research/Funding-Opportunities-Media-Folder/(Career-Development-Award|Innovative-Project-Award)\.pdf(\?sc_lang=en)?$'
          ))
      )
      AND jsonb_typeof(item->'fetched_at') = 'string'
      AND item->>'fetched_at' ~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$'
) AS allowed
WHERE fields.key IN ('title_normalized', 'sponsor_normalized', 'deadline_parsed',
                     'award_amount_parsed', 'deadline_precision', 'fetched_at')
  AND allowed.refs IS NOT NULL;
$$;

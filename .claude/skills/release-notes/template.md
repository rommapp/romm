<!--
Skeleton for a RomM alpha.1 / beta.1 release note. Drop any section that has no
content. A patch prerelease with no feat: work uses only the last two sections,
under a single `## What's Changed` heading.
-->

> [!WARNING]
> <Action the upgrader must take, in the imperative. Renamed config key, DB
> privilege the migration needs, proxy cache to purge. One warning per action.>

> [!NOTE]
>
> ### Environment variables
>
> | variable    | default | description                                |
> | ----------- | ------- | ------------------------------------------ |
> | NEW_ENV_VAR | `-`     | <what it does, and whether it is required> |
>
> ### API changes
>
> | Change            | Description                                                  |
> | ----------------- | ------------------------------------------------------------ |
> | `POST /api/thing` | <what it does>                                               |
> | `ThingSchema`     | <field added or changed; prefix the row with ⚠️ if breaking> |

## Highlights

### <Sentence case feature name>

<What it does, in one or two sentences, second person. Then the one thing the
reader needs in order to use it: the `config.yml` key, the setting, the caveat.
End with the bare PR reference.> #NNNN

```yaml
scan:
  some_key: true
```

<!-- screenshot: <what to capture> -->

## Minor changes

- feat(scope): <title> by @user in https://github.com/rommapp/romm/pull/NNNN

## Fixes

- fix(scope): <title> by @user in https://github.com/rommapp/romm/pull/NNNN

## Other changes

- perf(scope): <title> by @user in https://github.com/rommapp/romm/pull/NNNN
- build(deps): bump <pkg> from x to y by @dependabot[bot] in https://github.com/rommapp/romm/pull/NNNN

<!-- beta only, once the API table outgrows the top callout -->
<details>

<summary><h2>API changes</h2></summary>

| Change            | Description    |
| ----------------- | -------------- |
| `POST /api/thing` | <what it does> |

### <New endpoint group>

| Method | Path     | Description       |
| ------ | -------- | ----------------- |
| `GET`  | `/thing` | <what it returns> |

</details>

## New Contributors

- @user made their first contribution in https://github.com/rommapp/romm/pull/NNNN

**Full Changelog**: https://github.com/rommapp/romm/compare/<base stable tag>...<tag>

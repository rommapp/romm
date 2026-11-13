- every locale gets the key: A new translation key is added to every locale directory in the same change, never only to en_US.
  when: edit frontend/src/locales/en_US/*.json
  step: add the key to the same file in every locale directory
  step: run python3 src/locales/check_i18n_locales.py in frontend
  step: run python3 src/locales/check_i18n_sorted.py in frontend
  pitfall: a permission entity had no label, so the permissions matrix rendered the raw key settings.perm-entity.playlists (37b5b367f)
  learned: 37b5b367f, 5088a3bbc
  because: vue-i18n falls back to the raw key, so a missing locale entry shows users a dotted key instead of text

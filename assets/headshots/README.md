Headshots for the action list.

Drop a small square JPEG or PNG here, named for the lead owner's slug as
render_actions.py computes it:

    james-walker.jpg
    adriaan-mol.jpg
    jan-de-graaf.jpg
    angelo-nahavitatsara.jpg
    lanja-randriamanantena.jpg

The build picks the file up automatically and shows it beside the owner name
and on the owner chip. Where there is no file, the page draws the person's
initials instead - it never falls back to an external image and never
hot-links: assets/ is the only source, the same rule the partner logos follow.

These were not fetched from Microsoft 365. The connector this build uses is
granted User.ReadBasic.All but not People.Read, and exposes no user-photo
tool, so there is no way to read a profile photo from here. An administrator
granting those scopes, or anyone dropping the files in by hand, is all that is
needed - nothing else has to change.

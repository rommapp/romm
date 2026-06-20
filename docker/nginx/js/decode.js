// Decode a Base64 encoded string received as a query parameter named 'value',
// and return the decoded value in the response body.
function decodeBase64(r) {
  var encodedValue = r.args.value;

  if (!encodedValue) {
    r.return(400, "Missing 'value' query parameter");
    return;
  }

  try {
    // Use Buffer to return raw bytes — atob() returns a JS string which r.return()
    // would re-encode as UTF-8, corrupting any non-ASCII bytes (e.g. in filenames
    // like "Pokémon") and causing CRC mismatches in the mod_zip manifest.
    r.return(200, Buffer.from(encodedValue, 'base64'));
  } catch (e) {
    r.return(400, "Invalid Base64 encoding");
  }
}

export default { decodeBase64 };

// Decode a Base64 encoded string received as a query parameter named 'value',
// and return the decoded value in the response body.
function decodeBase64(r) {
  var encodedValue = r.args.value;

  if (!encodedValue) {
    r.return(400, "Missing 'value' query parameter");
    return;
  }

  try {
    var decodedValue = atob(encodedValue);
    r.return(200, decodedValue);
  } catch (e) {
    r.return(400, "Invalid Base64 encoding");
  }
}

export default { decodeBase64 };

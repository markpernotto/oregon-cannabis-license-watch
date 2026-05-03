# Certificate Bundle

`data.olcc.state.or.us` does not serve the intermediate certificate in its
TLS chain. Browsers cope because they cache the Sectigo intermediates;
strict HTTP clients (Python `requests`, Node fetch) fail with
`unable to get local issuer certificate`.

This directory ships the missing intermediate so the extractor can validate
the chain without disabling verification.

## File

- `sectigo_public_server_auth_ov_r36.pem` — Sectigo Public Server
  Authentication CA OV R36, valid through 2036-03-21. Sourced from the AIA
  extension of the OLCC server cert:
  http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt

## Refresh

If OLCC rotates to a different intermediate, the extractor will fail with a
TLS error pointing at a different `CA Issuers` URL. To refresh:

```
echo | openssl s_client -showcerts -connect data.olcc.state.or.us:443 \
  -servername data.olcc.state.or.us 2>/dev/null \
  | openssl x509 -noout -text \
  | grep -A1 "CA Issuers"
# Download the URL printed there, convert from DER to PEM, replace this file.
```

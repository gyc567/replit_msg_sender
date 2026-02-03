{ pkgs, python3 }:
let
  pyEnv = python3.withPackages (ps: [
    ps.requests
    ps.schedule
    ps.flask
    ps.aiohttp
  ]);
in
{
  deps = [ pyEnv ];
}

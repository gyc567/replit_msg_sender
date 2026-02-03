{ pkgs }:
let
  pyEnv = pkgs.python3.withPackages (ps: [
    ps.requests
    ps.schedule
    ps.flask
    ps.aiohttp
  ]);
in
{
  deps = [ pyEnv ];
}

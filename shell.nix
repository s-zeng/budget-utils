{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/refs/tags/25.05.tar.gz") {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
        cue
        ty
        python313
        python313Packages.polars
        python313Packages.requests
  ];
}

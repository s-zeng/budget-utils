{ pkgs ? import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/refs/tags/25.11.tar.gz") {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
        cue
        uv
  ];
}

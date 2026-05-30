class Ollamallm < Formula
  include Language::Python::Virtualenv

  desc "Recommend Ollama models based on your Mac or GPU hardware"
  homepage "https://github.com/zhmcoder/ollamallm"
  url "https://github.com/zhmcoder/ollamallm/releases/download/v0.1.2/ollamallm-0.1.2.tar.gz"
  sha256 "b003b90ad58c43ffa596c85adadee54b9b1a9723c3533ef9034c8d917751d85e"
  license "MIT"
  version "0.1.2"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/ollamallm help")
    assert_match "ollamallm", output
    assert_match "查本机", output
  end
end

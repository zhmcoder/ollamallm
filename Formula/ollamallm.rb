class Ollamallm < Formula
  include Language::Python::Virtualenv

  desc "Recommend Ollama models based on your Mac or GPU hardware"
  homepage "https://github.com/zhmcoder/ollamallm"
  url "https://github.com/zhmcoder/ollamallm/releases/download/v0.1.2/ollamallm-0.1.2.tar.gz"
  sha256 "ecf757ce7d304daed1b5e20937eac944187c7485b7d87b1be93051b8ab6368a8"
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

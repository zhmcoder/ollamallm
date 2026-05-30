class Ollamallm < Formula
  include Language::Python::Virtualenv

  desc "Recommend Ollama models based on your Mac or GPU hardware"
  homepage "https://github.com/zhmcoder/ollamallm"
  url "https://github.com/zhmcoder/ollamallm/releases/download/v0.1.0/ollamallm-0.1.0.tar.gz"
  sha256 "259a964ae2cba7de1ea35ff081bcd18f478ebbb884d7db806a42fb07cf59a662"
  license "MIT"
  version "0.1.0"

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

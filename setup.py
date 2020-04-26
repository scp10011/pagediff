from setuptools import setup, find_packages


def get_requirements():
    with open("requirements.txt") as requirements:
        return [
            line.split("#", 1)[0].strip()
            for line in filter(
                lambda x: x and not x.startswith(("#", "--", "git+")), requirements
            )
        ]


setup(
    name="pagediff",
    version="0.1",
    url="http://github.com/scp10011/pagediff",
    description="html page diff",
    license="Public",
    include_package_data=True,
    platforms=["GNU/Linux"],
    packages=find_packages("."),
    install_requires=get_requirements(),
    zip_safe=False,
    python_requires=">=3.6",
)

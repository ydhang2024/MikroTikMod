        license_key = bytes.fromhex(LICENSE_KEY)
        sign_key = bytes.fromhex(SIGN_KEY)

        npk.sign(license_key, sign_key)

        npk.save(output_npk)

        print("Output:", output_npk)

    finally:

        print("Cleaning workspace")

        shutil.rmtree(workdir)


def main():

    parser = argparse.ArgumentParser(
        prog="roswifi",
        description="RouterOS WIFI calibration patch tool"
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input NPK"
    )

    parser.add_argument(
        "-b",
        "--bdwlan",
        required=True,
        help="bdwlan directory"
    )

    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output NPK"
    )

    parser.add_argument(
        "--version",
        action="store_true"
    )

    args = parser.parse_args()

    if args.version:
        print("roswifi", VERSION)
        return

    check_tools()

    if not os.path.exists(args.input):
        print("Input NPK not found")
        sys.exit(1)

    if not os.path.exists(args.bdwlan):
        print("bdwlan directory not found")
        sys.exit(1)

    patch_bdwlan(
        args.input,
        args.bdwlan,
        args.output
    )


if __name__ == "__main__":
    main()

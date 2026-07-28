"""Print the deterministic DeepDelve 5.0 economy release gate."""

from deepdelve.systems.economy import economy_release_gate

if __name__ == "__main__":
    for days, result in economy_release_gate().items():
        print(
            f"{days:>2} days | earned {result['earned']:>7} | spent {result['spent']:>7} | "
            f"sink {result['sink_ratio']:.1%} | saved {result['saved']:>6} | "
            f"sanctum {result['sanctum_upgrades']:>2}/15",
        )

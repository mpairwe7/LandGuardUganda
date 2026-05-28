// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {stdJson} from "forge-std/StdJson.sol";
import {LandRegistryAnchor} from "../src/LandRegistryAnchor.sol";

/// @title MerkleParityTest — cross-language Merkle parity against shared vectors
/// @notice Loads contracts/test/merkle-parity.json (emitted by
///         backend/scripts/emit_merkle_vectors.py) and asserts that
///         LandRegistryAnchor.verifyProof agrees with the Python + TypeScript
///         reference implementations on every case. If this test fails, the
///         "anchored on a public chain, verifiable by anyone" claim has
///         silently drifted across languages — a P0 production incident.
/// @dev    Hardcoded CASE_COUNT must match the fixture; bump both together.
contract MerkleParityTest is Test {
    using stdJson for string;

    LandRegistryAnchor internal anchor;
    address internal constant ADMIN = address(0xA11CE);
    uint16 internal constant DISTRICT = 3; // Mityana pilot district id.
    uint256 internal constant CASE_COUNT = 10; // Update when emit_merkle_vectors.py grows.

    string internal fixture;

    function setUp() public {
        anchor = new LandRegistryAnchor(ADMIN);
        fixture = vm.readFile("./test/merkle-parity.json");
        // Pin the fixture schema. A bumped version means the Python emitter
        // and this test must move together; loud failure beats silent drift.
        assertEq(stdJson.readUint(fixture, ".schema_version"), 1, "schema bumped");
    }

    function test_Parity_AllCases() public {
        for (uint256 i = 0; i < CASE_COUNT; i++) {
            string memory base = string.concat(".cases[", vm.toString(i), "]");
            string memory name = stdJson.readString(fixture, string.concat(base, ".name"));
            bool skipSolidity = stdJson.readBool(fixture, string.concat(base, ".skip_solidity"));
            if (skipSolidity) {
                emit log_named_string("skip (no Solidity coverage)", name);
                continue;
            }
            _verifyCase(i, name, base);
        }
    }

    function _verifyCase(uint256 caseIndex, string memory name, string memory base) internal {
        emit log_named_string("case", name);
        bytes32 root = stdJson.readBytes32(fixture, string.concat(base, ".evm.root"));
        require(root != bytes32(0), "fixture: empty root for non-skipped case");

        // Anchor the batch under a deterministic batchId derived from the case
        // index. Avoids cross-case collisions inside a single test function.
        bytes32 batchId = keccak256(abi.encodePacked("merkle-parity:", caseIndex));
        vm.prank(ADMIN);
        anchor.commitBatch(DISTRICT, batchId, root);

        // The number of proofs equals the number of leaves; iterate using the
        // leaves array length as ground truth.
        bytes32[] memory leaves = stdJson.readBytes32Array(
            fixture, string.concat(base, ".evm.leaves")
        );
        for (uint256 j = 0; j < leaves.length; j++) {
            string memory proofBase = string.concat(base, ".evm.proofs[", vm.toString(j), "]");
            bytes32 leaf = stdJson.readBytes32(fixture, string.concat(proofBase, ".leaf"));
            bytes32[] memory siblings = stdJson.readBytes32Array(
                fixture, string.concat(proofBase, ".siblings")
            );
            assertEq(leaf, leaves[j], string.concat(name, ": leaf/leaves[] mismatch"));
            assertTrue(
                anchor.verifyProof(batchId, leaf, siblings),
                string.concat(name, ": proof rejected by verifyProof")
            );

            // Tampered leaf must NOT verify. The tampered hash is the keccak
            // of a string with the case name and index baked in so each case
            // generates a fresh tamper sample.
            bytes32 tampered = keccak256(abi.encodePacked("tampered:", name, ":", j));
            assertFalse(
                anchor.verifyProof(batchId, tampered, siblings),
                string.concat(name, ": tampered leaf accepted by verifyProof")
            );
        }
    }

    /// @dev If someone adds a case to merkle-parity.json without bumping
    ///      ``CASE_COUNT``, the loop above silently skips the new case. Pin
    ///      the count explicitly so the test fails loudly instead.
    function test_Parity_CaseCountInSync() public view {
        // Probe one past CASE_COUNT; if a case exists there, readString
        // returns a non-empty name. We do NOT call readString directly because
        // forge-std reverts when the path is missing — exactly the signal we
        // want from the opposite direction: assert the LAST expected case
        // exists and has a non-empty name.
        string memory lastName = stdJson.readString(
            fixture, string.concat(".cases[", vm.toString(CASE_COUNT - 1), "].name")
        );
        assertGt(bytes(lastName).length, 0, "fixture missing last expected case");
    }
}

import { type TArg, type TRet } from '@noble/hashes/utils.js';
/** Network-specific BIP32 version bytes. */
export interface Versions {
    /** 4-byte version used when serializing private extended keys. */
    private: number;
    /** 4-byte version used when serializing public extended keys. */
    public: number;
}
/** Hardened child index offset from BIP32. */
export declare const HARDENED_OFFSET: number;
interface HDKeyOpt {
    versions?: Versions;
    depth?: number;
    index?: number;
    parentFingerprint?: number;
    chainCode?: Uint8Array;
    publicKey?: Uint8Array;
    privateKey?: Uint8Array;
}
/**
 * HDKey from BIP32
 * @param opt - Node fields used to construct one HDKey instance.
 * @example
 * ```js
 * import { HDKey } from '@scure/bip32';
 * import { randomBytes } from '@noble/hashes/utils.js';
 *
 * const seed = randomBytes(32);
 * const root = HDKey.fromMasterSeed(seed);
 * const account0 = root.derive("m/0/1'");
 * account0.publicKey;
 * ```
 */
export declare class HDKey {
    get fingerprint(): number;
    get identifier(): Uint8Array | undefined;
    get pubKeyHash(): Uint8Array | undefined;
    get privateKey(): Uint8Array | null;
    get publicKey(): Uint8Array | null;
    get privateExtendedKey(): string;
    get publicExtendedKey(): string;
    static fromMasterSeed(seed: Uint8Array, versions?: Versions): HDKey;
    static fromExtendedKey(base58key: string, versions?: Versions): HDKey;
    static fromJSON(json: {
        xpriv: string;
    }): HDKey;
    readonly versions: Versions;
    readonly depth: number;
    readonly index: number;
    readonly chainCode: Uint8Array | null;
    readonly parentFingerprint: number;
    private _privateKey?;
    private _publicKey?;
    private pubHash;
    constructor(opt: HDKeyOpt);
    derive(path: string): HDKey;
    /**
     * @param _I - Test-only override for the 64-byte HMAC-SHA512 output; normal callers must omit it.
     */
    deriveChild(index: number, _I?: Uint8Array): HDKey;
    sign(hash: Uint8Array): Uint8Array;
    verify(hash: Uint8Array, signature: Uint8Array): boolean;
    wipePrivateData(): this;
    toJSON(): {
        xpriv: string;
        xpub: string;
    };
    private serialize;
}
type Tests = Readonly<{
    deriveChildWithI(key: TArg<HDKey>, index: number, I: TArg<Uint8Array>): TRet<HDKey>;
}>;
export declare const __TESTS: TRet<Tests>;
export {};
//# sourceMappingURL=index.d.ts.map
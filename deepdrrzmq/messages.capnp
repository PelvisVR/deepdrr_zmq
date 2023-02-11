@0xeaa72c8788903898;

struct Optional(Value) {
    union {
        value @0 :Value;
        none @1 :Void;
    }
}

struct OptionalFloat32 {
    union {
        value @0 :Float32;
        none @1 :Void;
    }
}

struct Time {
  millis @0 :UInt64;
}

struct Matrix3x3{
  data @0 :List(Float32);
}

struct Matrix4x4 {
  data @0 :List(Float32);
}

struct Image {
  data @0 :Data;
}

struct CameraIntrinsics {
    sensorHeight @0 :UInt32 = 1536;
    sensorWidth @1 :UInt32 = 1536;
    pixelSize @2 :Float32 = 0.194;
    sourceToDetectorDistance @3 :Float32 = 1020;
}

struct CameraProjection {
    intrinsic @0 :CameraIntrinsics;
    extrinsic @1 :Matrix4x4;
}

struct Device {
    camera @0 :CameraProjection;
}

struct NiftiLoaderParams {
    path @0 :Text;
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool = true;
    useCached @3 :Bool = true;
    saveCache @4 :Bool = false;
    cacheDir @5 :Optional(Text) = (none = void);
#   materials @? :List(Text);
    segmentation @6 :Bool = false;
#    densityKwargs @? :List(Text);
}

struct DicomLoaderParams { # todo
    path @0 :Text;
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool = true;
    useCached @3 :Bool = true;
    saveCache @4 :Bool = false;
    cacheDir @5 :Optional(Text) = (none = void);
#   materials @? :List(Text);
    segmentation @6 :Bool = false;
#    densityKwargs @? :List(Text);
}

struct VolumeLoaderParams {
    union {
        nifti @0 :NiftiLoaderParams;
        dicom @1 :DicomLoaderParams;
    }
}

struct ProjectorParams {
    volumes @0 :List(VolumeLoaderParams);
    priorities @1 :List(UInt32);
    device @2 :Device;
    step @3 :Float32 = 0.1;
    mode @4 :Text = "linear";
    spectrum @5 :Text = "90KV_AL40";
    scatterNum @6 :UInt32 = 0;
    addNoise @7 :Bool = false;
    photonCount @8 :UInt32 = 10000;
    threads @9 :UInt32 = 8;
    maxBlockIndex @10 :UInt32 = 1024;
    collectedEnergy @11 :Bool = false;
    neglog @12 :Bool = true;
    intensityUpperBound @13 :OptionalFloat32 = (none = void);
    attenuateOutsideVolume @14 :Bool = false;
}

struct StatusResponse {
#    success @0 :Bool;
    code @0 :UInt16;
    message @1 :Text;
}

struct ProjectRequest {
    requestId @0 :Text;
    projectorId @1 :Text;
    cameraProjections @2 :List(CameraProjection);
    volumesWorldFromAnatomical @3 :List(Matrix4x4);
}

struct ProjectResponse {
    requestId @0 :Text;
    projectorId @1 :Text;
    status @2 :StatusResponse;
    images @3 :List(Image);
}

struct ProjectorParamsResponse {
    projectorId @0 :Text;
    projectorParams @1 :ProjectorParams;
}

struct ProjectorParamsRequest {
    projectorId @0 :Text;
}
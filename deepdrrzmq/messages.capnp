@0xeaa72c8788903898;

struct OptionalFloat32 {
    union {
        value @0 :Float32;
        none @1 :Void;
    }
}

struct OptionalText {
    union {
        value @0 :Text;
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

struct CameraProjection {
    intrinsic @0 :Matrix3x3;
    extrinsic @1 :Matrix4x4;
}

struct NiftiLoaderParams {
    path @0 :Text;
    worldFromAnatomical @1 :Matrix4x4;
    useThresholding @2 :Bool = true;
    useCached @3 :Bool = true;
    saveCache @4 :Bool = false;
    cacheDir @5 :OptionalText = (none = void);
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
    cacheDir @5 :OptionalText = (none = void);
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
    step @2 :Float32 = 0.1;
    mode @3 :Text = "linear";
    spectrum @4 :Text = "90KV_AL40";
    scatterNum @5 :UInt32 = 0;
    addNoise @6 :Bool = false;
    photonCount @7 :UInt32 = 10000;
    threads @8 :UInt32 = 8;
    maxBlockIndex @9 :UInt32 = 1024;
    collectedEnergy @10 :Bool = false;
    neglog @11 :Bool = true;
    intensityUpperBound @12 :OptionalFloat32 = (none = void);
    attenuateOutsideVolume @13 :Bool = false;
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

struct CreateProjectorRequest {
    projectorId @0 :Text;
    projectorParams @1 :ProjectorParams;
}

struct DeleteProjectorRequest {
    projectorId @0 :Text;
}

struct ServerCommand {
    union {
        createProjector @0 :CreateProjectorRequest;
        deleteProjector @1 :DeleteProjectorRequest;
    }
}
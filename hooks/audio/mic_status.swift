import CoreAudio

var propAddr = AudioObjectPropertyAddress(
    mSelector: kAudioHardwarePropertyDefaultInputDevice,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
)
var deviceID = AudioDeviceID(kAudioObjectUnknown)
var propSize = UInt32(MemoryLayout<AudioDeviceID>.size)
AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &propAddr, 0, nil, &propSize, &deviceID)

var runAddr = AudioObjectPropertyAddress(
    mSelector: kAudioDevicePropertyDeviceIsRunningSomewhere,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
)
var isRunning: UInt32 = 0
propSize = UInt32(MemoryLayout<UInt32>.size)
AudioObjectGetPropertyData(deviceID, &runAddr, 0, nil, &propSize, &isRunning)
exit(isRunning > 0 ? 0 : 1)

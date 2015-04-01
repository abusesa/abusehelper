"""
An example bot for controlling a VirtualBox-based sandbox. Assumptions:

 * Shared input and output directories between host and guest
 * The file "script.bat" in the share dir is executed at vm startup
 * There is a clean state which the sandbox is reverted at exit
 * Sandbox generates outout which you can analyze with a script/executable

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import os
import idiokit

from subprocess import Popen, PIPE, STDOUT

from abusehelper.core import bot, events
from abusehelper.bots.experts.combiner import Expert

from opencollab.wiki import GraphingWiki
from opencollab.util.file import uploadFile


def run_command(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=STDOUT,
              shell=True, close_fds=True)
    return p.stdout.read(), p.returncode


class Continue(Exception):
    pass


class VirtualboxSandboxExpert(Expert):
    collab_url = bot.Param()
    collab_user = bot.Param()
    collab_password = bot.Param()
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)

    vmname = bot.Param("Sandbox name in VirtualBox")
    snapshotname = bot.Param("Clean snapshot name of VM")
    scriptdir = bot.Param("Directory for startup script on host")
    indir = bot.Param("Input directory on host")
    indir_win = bot.Param("Input directory on guest")
    outdir = bot.Param("Output directory on host")
    outdir_win = bot.Param("Output directory on guest")
    timeout = bot.IntParam("Timeout", default=120)
    script_name = bot.Param("The name of the script guest runs",
                            default="script.bat")
    sample_name = bot.Param("The name of the sample guest runs",
                            default="sample.exe")
    analysisfile = bot.Param("", default="logger.bin")
    sandparser = bot.Param("Sandbox parser", default=None)

    script = bot.Param("Script to run at VM startup", default="")

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.cache = dict()

        self.collab = GraphingWiki(self.collab_url,
                                   ssl_verify_cert=not self.collab_ignore_cert,
                                   ssl_ca_certs=self.collab_extra_ca_certs)
        self.collab.authenticate(self.collab_user, self.collab_password)

        self.script = self.script % self.__dict__
        file(os.path.join(self.scriptdir, 'script.bat'),
             'wb').write(self.script.encode('cp1252').replace('\n', '\r\n'))
        self.log.info("Started with script %s", self.script)

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("md5",)))

    def upload_analysis(self, md5sum, analysis, screenshot):
        page = md5sum
        metas = {'screenshot': ['{{attachment:screenshot.png}}'],
                 'analysis': ['[[attachment:analysis.txt]]']}
        result = self.collab.setMeta(page, metas, True)
        for line in result:
            self.log.info("%r: %r", page, line)

        scdata = file(screenshot).read()
        for data, fname in [(analysis, "analysis.txt"),
                            (scdata, "screenshot.png")]:
            if not data:
                continue
            try:
                self.log.info("Uploading file: %r (data %r...)",
                              fname, repr(data[:10]))
                uploadFile(self.collab, page, '', fname, data=data)
            except (IOError, TypeError, RuntimeError), msg:
                self.log.error("Upload failed: %r", msg)
                return

        return True

    def get_attachment(self, md5sum):
        return self.collab.getAttachment(md5sum, 'content.raw')

    @idiokit.stream
    def _run_command(self, cmd, *args):
        out, s = yield idiokit.thread(run_command, cmd % args)
        if s:
            self.log.error(out)
            raise Continue()
        idiokit.stop(out)

    @idiokit.stream
    def augment(self, key):
        while True:
            eid, event = yield idiokit.next()

            for md5sum in event.values(key):
                new = events.Event()

                try:
                    # Grab malware from wiki
                    self.log.info("Getting %r from wiki", md5sum)
                    data = yield idiokit.thread(
                        self.get_attachment, md5sum)

                    # Put sample in place
                    file(os.path.join(self.indir, self.sample_name),
                         'wb').write(data)

                    self.log.info("Starting sandbox run for %r", md5sum)
                    # Stop vm if running
                    out = yield self._run_command("VBoxManage list runningvms")

                    if self.vmname in out:
                        self.log.info("vm was running, stopping")
                        yield self._run_command(
                            "VBoxManage controlvm %s poweroff", self.vmname)

                    # Restore snapshot
                    yield self._run_command("VBoxManage snapshot %s restore %s",
                                            self.vmname, self.snapshotname)

                    # Start vm
                    yield self._run_command(
                        "VBoxManage startvm %s --type headless", self.vmname)

                    # Sleep for a bit more than the timeout
                    yield idiokit.sleep(int(self.timeout) * 2)

                    # Take a screenshot
                    yield self._run_command(
                        "VBoxManage controlvm %s screenshotpng %s",
                        self.vmname,
                        os.path.join(self.outdir, "screenshot.png"))

                    # Power off vm
                    yield self._run_command("VBoxManage controlvm %s poweroff",
                                            self.vmname)

                    # Restore vm to snapshot
                    yield self._run_command("VBoxManage snapshot %s restore %s",
                                            self.vmname, self.snapshotname)

                    # Run analysis
                    analysis = yield self._run_command("%s %s/%s",
                                                       self.sandparser,
                                                       self.outdir,
                                                       self.analysisfile)

                    self.log.info("Done with sandbox run for %r", md5sum)
                    # Upload to wiki
                    yield idiokit.thread(self.upload_analysis, md5sum,
                        analysis,
                        os.path.join(self.outdir,
                                     "screenshot.png"))

                    # Cleanup
                    for dn, fn in ((self.outdir, 'logger.bin'),
                                   (self.outdir, 'screenshot.png'),
                                   (self.outdir, 'report.txt'),
                                   (self.indir, 'sample.exe')):
                        if os.path.isfile(os.path.join(dn, fn)):
                            os.unlink(os.path.join(dn, fn))
                except Continue:
                    continue
                else:
                    new.add("sandbox analysis", self.collab_url + md5sum)

                yield idiokit.send(eid, new)


if __name__ == "__main__":
    VirtualboxSandboxExpert.from_command_line().execute()

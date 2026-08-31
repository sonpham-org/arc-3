"""a010 Spare Path -- schedule a reusable track tile across degrading machines."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DEPOT,MACHINE,TRACK,SPARE,RUN,QUOTA,GOAL,BAD=9,10,14,6,11,12,5,13,15
LEVELS=[{"name":"First Cycle","seq":(1,)},{"name":"Stopped Machine","seq":(2,1)},{"name":"Move Spare","seq":(3,1,2)},{"name":"Preventive Switch","seq":(4,2,1,3)},{"name":"Three Quotas","seq":(2,3,1,4,2,1)},{"name":"Spare Path","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 tracks,quota,active,stopped,spare,history,scheduled=s;t=list(tracks);q=list(quota)
 if a==1:
  for i in range(3):
   if i!=stopped:t[i]=max(0,t[i]-1);q[i]+=int(t[i]>0)
  history=history+((tuple(t),tuple(q),active,stopped,spare),)
 elif a==2:stopped=active if stopped!=active else -1
 elif a==3:
  if stopped>=0:spare=stopped;t[stopped]=min(4,t[stopped]+1)
 elif a==4:active=(active+1)%3;stopped=-1
 elif a==5:scheduled=(tuple(t),tuple(q),active,stopped,spare,history[-4:])
 return tuple(t),tuple(q),active,stopped,spare,history,scheduled
for x in LEVELS:
 s=((4,3,2),(0,0,0),0,-1,-1,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DEPOT
  for i,(t,q) in enumerate(zip(g.tracks,g.quota)):x=8+i*18;f[8:31,x:x+13]=MACHINE;f[25-t*4:29,x+2:x+11]=TRACK;f[10:14,x+3:x+10]=RUN if i==g.active else QUOTA;f[33:37,x:x+2+q*2]=QUOTA
  if g.spare>=0:x=8+g.spare*18;f[40:46,x:x+13]=SPARE
  for i,_ in enumerate(g.history[-3:]):f[50:54,8+i*14:18+i*14]=RUN
  if g.scheduled:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A010(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a010",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tracks=(4,3,2);self.quota=(0,0,0);self.active=0;self.stopped=self.spare=-1;self.history=();self.scheduled=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tracks,self.quota,self.active,self.stopped,self.spare,self.history,self.scheduled=advance((self.tracks,self.quota,self.active,self.stopped,self.spare,self.history,self.scheduled),a)
  elif a==6:
   if (self.tracks,self.quota,self.active,self.stopped,self.spare,self.history,self.scheduled)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

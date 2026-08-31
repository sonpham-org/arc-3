"""q771 Aurora Rhythm -- chunk routines and interrupt at state-defined windows."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,RHYTHM,CHUNK,HYSTERESIS,WINDOW,BAD=8,10,12,14,6,11,5,7,15
def make(name,period,body):
 phase=macro=control=hyst=0
 for a in body:
  if a in (1,2,3):total=phase+a;macro+=total//period;phase=total%period;control=a-1
  else:control=(control-1)%3;hyst=(hyst+2)%5;total=phase+hyst;macro+=total//period;phase=total%period
 return {"name":name,"period":period,"window":phase,"plan":tuple(body)+(5,)}
LEVELS=[make("One Chunk",3,(1,2)),make("Scaled Interval",4,(2,3)),make("Repeated Routine",5,(1,2,3)),make("Control Return",6,(1,2,3,4)),make("Hysteretic Window",7,(2,3,4,1,2)),make("Aurora Rhythm",8,(3,1,2,4,3,2,1))]
def advance(s,a,x):
 phase,macro,control,hyst,chunks,interrupted=s;chunks=list(chunks)
 if a in (1,2,3):total=phase+a;macro+=total//x["period"];phase=total%x["period"];control=a-1;chunks.append((a,phase,macro))
 elif a==4:control=(control-1)%3;hyst=(hyst+2)%5;total=phase+hyst;macro+=total//x["period"];phase=total%x["period"];chunks.append((4,phase,macro,hyst))
 elif a==5:
  if phase!=x["window"] or macro<1:return None
  interrupted=(phase,macro,control,hyst,tuple(chunks))
 return phase,macro,control,hyst,tuple(chunks),interrupted
def target(x):
 s=(0,0,0,0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,c in enumerate(g.chunks[-8:]):x=9+(i%4)*12;y=11+(i//4)*10;f[y:y+6,x:x+9]=MOTE-(c[0]%3)
  f[37:40,8:11+g.phase*6]=RHYTHM;f[44:47,8:11+(g.macro%5)*9]=CHUNK;f[50:53,8:11+g.hyst*9]=HYSTERESIS;f[55:58,40:56]=WINDOW
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q771(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q771",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=self.macro=self.control=self.hyst=0;self.chunks=();self.interrupted=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.phase,self.macro,self.control,self.hyst,self.chunks,self.interrupted),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.phase,self.macro,self.control,self.hyst,self.chunks,self.interrupted=s
  elif a==6:
   if (self.phase,self.macro,self.control,self.hyst,self.chunks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

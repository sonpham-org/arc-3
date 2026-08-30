"""q437 Spectrum Revision -- revise a worn transformation law across visual domains."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,PACKET,WEAR,DOMAIN,DELAY,RULE,BAD=0,1,15,9,12,14,10,11,8
LEVELS=[
 {"name":"Old Spectrum","boundary":3,"mode":1,"plan":(1,2)},
 {"name":"Wear Cue","boundary":2,"mode":2,"plan":(2,1,4)},
 {"name":"Inverted Pane","boundary":2,"mode":3,"plan":(3,2,5,1)},
 {"name":"Geometry Transfer","boundary":3,"mode":2,"plan":(1,4,5,2,3)},
 {"name":"Delayed Revision","boundary":2,"mode":1,"plan":(2,3,4,1,5,2)},
 {"name":"Spectrum Revision","boundary":3,"mode":3,"plan":(3,1,5,2,4,3,1,5)}]
def advance(s,a,x):
 symbols,wear,domain,delay,cued=s;symbols=list(symbols)
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:symbols[i]=(symbols[i]+a+domain)%4
  elif rule==2:symbols[i]=3-symbols[i]
  else:delay=(delay+a+i)%4
  wear+=1
 elif a==4:cued=True;symbols=[(v+delay)%4 for v in symbols];delay=0
 elif a==5:domain=1-domain;symbols=([(v*3+1)%4 for v in symbols] if domain else [(v+1)%4 for v in symbols])
 return tuple(symbols),wear,domain,delay,cued
def target(x):
 s=((0,1,2),0,0,0,False)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GALLERY;f[9:20,25:39]=PRISM
  for i,v in enumerate(g.symbols):x=8+i*18;f[27:36,x:x+12]=PACKET+v%3;f[37:40,x:x+v*3]=RULE
  f[44:47,8:8+min(g.wear,8)*6]=WEAR;f[49:52,8:8+g.domain*24]=DOMAIN;f[54:57,8:8+g.delay*12]=DELAY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q437(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q437",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.symbols=(0,1,2);self.wear=0;self.domain=0;self.delay=0;self.cued=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.symbols,self.wear,self.domain,self.delay,self.cued=advance((self.symbols,self.wear,self.domain,self.delay,self.cued),a,x)
  elif a==6:
   if (self.symbols,self.wear,self.domain,self.delay,self.cued)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()

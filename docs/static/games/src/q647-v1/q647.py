"""q647 Spectrum Sandbox -- reset prism trials while wavelength evidence persists."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,PRISM,PACKET,PANE,EVIDENCE,RESET,GOAL,BAD=4,9,11,14,10,6,12,13,15
LEVELS=[
 {"name":"First Trial","seq":(1,3)},{"name":"Split Pane","seq":(2,3,4)},
 {"name":"Persistent Spectrum","seq":(1,3,4,2,3)},{"name":"Relational Contrast","seq":(2,1,3,4,1,3)},
 {"name":"Two Hypotheses","seq":(1,2,3,4,2,2,3)},
 {"name":"Spectrum Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 packets,pane,split,evidence,trials,commit=s;v=list(packets)
 if a==1:v[0],v[1]=v[1],v[0];pane=(pane+1)%4
 elif a==2:v=v[1:]+v[:1];split=(split+1+pane)%5;pane=(pane+2)%4
 elif a==3:evidence=evidence+((tuple(v),pane,split),);trials+=1
 elif a==4:v[:]=[0,2,4];pane=split=0
 elif a==5:commit=(tuple(v),pane,split,evidence[-3:],trials)
 return tuple(v),pane,split,evidence,trials,commit
for x in LEVELS:
 s=((0,2,4),0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=PRISM;f[8:31,35:57]=RESET
  for i,p in enumerate(g.packets):x=9+i*7;f[24-p*3:29,x:x+6]=PACKET
  for i,e in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+e[2]]=PANE
  f[50:54,8:8+g.pane*11+7]=PANE;f[55:59,8:8+g.split*9+6]=PRISM
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q647(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q647",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.packets=(0,2,4);self.pane=self.split=self.trials=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.packets,self.pane,self.split,self.evidence,self.trials,self.commit=advance((self.packets,self.pane,self.split,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.packets,self.pane,self.split,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

"""a005 Leaking Loop -- triangulate a seam from conservation residuals under valve changes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLANT,PIPE,FLUID,GAUGE,VALVE,RESIDUAL,GOAL,BAD=4,10,8,14,6,11,12,13,15
LEVELS=[{"name":"First Gauge","seq":(1,3)},{"name":"Second Gauge","seq":(2,3)},{"name":"Valve Contrast","seq":(1,2,3)},{"name":"Loop Reversal","seq":(4,2,1,3)},{"name":"Residual Triangle","seq":(2,3,1,4,2,1,3)},{"name":"Leaking Loop","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 gauges,valve,fluid,leak,evidence,patched=s;g=list(gauges)
 if a==1:g[0]=(g[0]+1)%8
 elif a==2:g[1]=(g[1]+3)%8
 elif a==3:p=tuple((fluid-abs(x-leak)-valve*2)%9 for x in g);residual=(sum(p)+fluid-leak)%7;evidence=evidence+((tuple(g),valve,p,residual),);fluid=max(1,fluid-1)
 elif a==4:valve=(valve+1)%3;fluid=(fluid+2)%9 or 8
 elif a==5:patched=(leak,tuple(g),valve,fluid,evidence[-4:])
 return tuple(g),valve,fluid,leak,evidence,patched
for x in LEVELS:
 s=((0,4),0,8,6,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLANT;f[9:15,10:54]=PIPE;f[15:34,48:54]=PIPE;f[28:34,10:54]=PIPE;f[15:34,10:16]=PIPE;f[11:13,12:52]=FLUID
  for i,p in enumerate(g.gauges):x=9+(p%4)*13;y=18+(p//4)*9;f[y:y+7,x:x+9]=GAUGE
  for i,(_,v,press,r) in enumerate(g.evidence[-4:]):x=8+i*12;f[39:45,x:x+9]=RESIDUAL;f[46:49,x:x+2+r]=FLUID;f[50:53,x:x+2+v*2]=VALVE
  if g.patched:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A005(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a005",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.gauges=(0,4);self.valve=0;self.fluid=8;self.leak=6;self.evidence=();self.patched=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.gauges,self.valve,self.fluid,self.leak,self.evidence,self.patched=advance((self.gauges,self.valve,self.fluid,self.leak,self.evidence,self.patched),a)
  elif a==6:
   if (self.gauges,self.valve,self.fluid,self.leak,self.evidence,self.patched)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()

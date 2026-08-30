"""q237 Lantern Accord -- infer a coalition rule and align its shared pledge."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,LANTERN,VOICE,PLEDGE,RULE,BAD=12,6,14,2,10,15,8
SIGNALS=((1,2,1),(2,1,3),(3,2,2),(1,3,3))
LEVELS=[{"name":n,"rule":r,"need":need,"pledge":p} for n,r,need,p in [
 ("First Greeting",0,(1,),2),("Paired Courtesy",1,(1,2),1),("Dissenting Guest",2,(2,3),3),
 ("Coalition Table",3,(1,2,3),2),("Reversed Etiquette",1,(1,3),0),("Lantern Accord",2,(1,2,3),1)]]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,5:59]=HALL
  for i in range(3):
   x=10+i*17;f[11:25,x:x+10]=LANTERN if g.seen&(1<<i) else VOICE
  f[32:37,8:8+g.pledge*12]=PLEDGE;f[44:49,8:8+g.candidate*11]=RULE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q237(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.pledge=self.candidate=0;self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q237",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.pledge=self.candidate=0;self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.seen|=1<<(a-1);self.pledge=(self.pledge+SIGNALS[x["rule"]][a-1])%4
  elif a==4:self.candidate=(self.candidate+1)%4
  elif a==6:self.pledge=(self.pledge+1)%4
  elif a==5:
   mask=sum(1<<(i-1) for i in x["need"])
   if self.seen&mask==mask and self.candidate==x["rule"] and self.pledge==x["pledge"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
